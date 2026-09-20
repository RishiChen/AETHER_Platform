from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageStat

try:
    import torch
    import open_clip
except ImportError:
    torch = None
    open_clip = None


class LocalCVFallbackModel:
    """
    Lightweight offline encoder for small local datasets. It is not a RemoteCLIP
    replacement, but it gives deterministic visual vectors instead of random
    model output when full pretrained weights are unavailable.
    """

    signature = "local-cv-fallback-v1"

    def _normalize(self, vector):
        vector = np.asarray(vector, dtype=np.float32)
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm

    def encode_image(self, image):
        image = image.convert("RGB").resize((128, 128))
        arr = np.asarray(image, dtype=np.float32) / 255.0
        gray = np.asarray(image.convert("L"), dtype=np.float32) / 255.0

        channels = [arr[:, :, idx] for idx in range(3)]
        means = [float(channel.mean()) for channel in channels]
        stds = [float(channel.std()) for channel in channels]

        hist_features = []
        for channel in channels:
            hist, _ = np.histogram(channel, bins=32, range=(0.0, 1.0), density=True)
            hist_features.extend(hist.tolist())

        gray_hist, _ = np.histogram(gray, bins=32, range=(0.0, 1.0), density=True)
        edges = image.convert("L").filter(ImageFilter.FIND_EDGES)
        edge_arr = np.asarray(edges, dtype=np.float32) / 255.0
        edge_hist, _ = np.histogram(edge_arr, bins=32, range=(0.0, 1.0), density=True)

        texture = []
        for size in (2, 4, 8, 16):
            small = image.convert("L").resize((size, size))
            stat = ImageStat.Stat(small)
            texture.append(float(stat.mean[0]) / 255.0)
            texture.append(float(stat.stddev[0]) / 255.0)

        r, g, b = channels
        blue_ratio = float((b > r + 0.08).mean())
        green_ratio = float((g > r + 0.05).mean())
        bare_ratio = float(((r > 0.38) & (g > 0.32) & (b < 0.34)).mean())
        bright_ratio = float((gray > 0.72).mean())
        dark_ratio = float((gray < 0.25).mean())
        edge_density = float((edge_arr > 0.22).mean())

        gx = np.abs(np.diff(gray, axis=1))
        gy = np.abs(np.diff(gray, axis=0))
        horizontal_strength = float(gy.mean())
        vertical_strength = float(gx.mean())
        linearity = abs(horizontal_strength - vertical_strength)

        features = [
            *means,
            *stds,
            *hist_features,
            *gray_hist.tolist(),
            *edge_hist.tolist(),
            *texture,
            blue_ratio,
            green_ratio,
            bare_ratio,
            bright_ratio,
            dark_ratio,
            edge_density,
            horizontal_strength,
            vertical_strength,
            linearity,
        ]

        category_features = self._image_category_features(
            blue_ratio=blue_ratio,
            green_ratio=green_ratio,
            bare_ratio=bare_ratio,
            bright_ratio=bright_ratio,
            edge_density=edge_density,
            linearity=linearity,
        )

        vector = np.zeros(512, dtype=np.float32)
        usable = min(len(features), 480)
        vector[:usable] = np.asarray(features[:usable], dtype=np.float32)
        vector[480:480 + len(category_features)] = category_features * 8.0
        return self._normalize(vector)

    def encode_text(self, text):
        text = (text or "").lower()
        vector = np.zeros(512, dtype=np.float32)

        keyword_groups = {
            480: ("river", "stream", "canal", "bridge", "waterway", "floodplain"),
            481: ("highway", "road", "expressway", "linear", "corridor", "asphalt"),
            482: ("water", "reservoir", "lake", "shoreline", "pond", "hydro"),
            483: ("industry", "industrial", "port", "warehouse", "terminal", "tank", "yard"),
            484: ("cleared", "clearing", "deforestation", "bare", "soil", "settlement"),
            485: ("urban", "city", "building", "built", "structure", "construction"),
        }

        for idx, words in keyword_groups.items():
            vector[idx] = sum(1.0 for word in words if word in text)

        if not vector[480:486].any():
            tokens = [token for token in text.replace("-", " ").replace("_", " ").split() if token]
            for token in tokens:
                vector[486 + (sum(ord(ch) for ch in token) % 20)] += 0.25

        return self._normalize(vector)

    def _image_category_features(self, blue_ratio, green_ratio, bare_ratio, bright_ratio, edge_density, linearity):
        water = max(blue_ratio, min(1.0, blue_ratio + dark_ratio_like(blue_ratio, bright_ratio)))
        highway = min(1.0, edge_density * 1.8 + linearity * 3.0)
        industry = min(1.0, edge_density * 2.0 + bright_ratio * 0.8)
        cleared = min(1.0, bare_ratio * 2.5 + (1.0 - green_ratio) * 0.25)
        river = min(1.0, water * 0.7 + linearity * 2.0)
        urban = min(1.0, edge_density * 1.5 + bright_ratio * 0.4)
        return np.asarray([river, highway, water, industry, cleared, urban], dtype=np.float32)


def dark_ratio_like(blue_ratio, bright_ratio):
    return max(0.0, blue_ratio - bright_ratio * 0.35)


class RemoteCLIPModel:
    signature = "remoteclip-vit-b-32"

    def __init__(self):
        self.device = "cpu"
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self.fallback = None

        data_dir = Path(__file__).resolve().parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = data_dir / "RemoteCLIP-ViT-B-32.pt"

        can_load_remoteclip = (
            torch is not None
            and open_clip is not None
            and checkpoint_path.exists()
            and checkpoint_path.stat().st_size > 300_000_000
        )

        if can_load_remoteclip:
            print("Loading RemoteCLIP weights from", checkpoint_path)
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32",
                pretrained=None,
            )
            state_dict = torch.load(checkpoint_path, map_location="cpu")
            self.model.load_state_dict(state_dict)
            self.model = self.model.to(self.device)
            self.model.eval()
            self.tokenizer = open_clip.get_tokenizer("ViT-B-32")
            print("Device:", self.device)
            print("RemoteCLIP loaded successfully")
            return

        print("Full RemoteCLIP weights are unavailable; using deterministic local CV fallback encoder.")
        self.fallback = LocalCVFallbackModel()
        self.signature = self.fallback.signature

    def encode_image(self, image):
        if self.fallback is not None:
            return self.fallback.encode_image(image)

        image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            embedding = self.model.encode_image(image_tensor)
        embedding = embedding / embedding.norm(dim=-1, keepdim=True)
        return embedding.cpu().numpy()[0]

    def encode_text(self, text):
        if self.fallback is not None:
            return self.fallback.encode_text(text)

        text_tokens = self.tokenizer([text]).to(self.device)
        with torch.no_grad():
            embedding = self.model.encode_text(text_tokens)
        embedding = embedding / embedding.norm(dim=-1, keepdim=True)
        return embedding.cpu().numpy()[0]
