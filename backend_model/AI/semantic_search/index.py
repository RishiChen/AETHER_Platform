try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    faiss = None
    FAISS_AVAILABLE = False

import os
import numpy as np


class ImageIndex:

    def __init__(self, dimension):
        self.dimension = dimension
        self.use_faiss = FAISS_AVAILABLE
        self.ids = []
        self.matrix = np.empty((0, dimension), dtype=np.float32)

        if self.use_faiss:
            base_index = faiss.IndexFlatIP(dimension)
            self.index = faiss.IndexIDMap(base_index)
        else:
            self.index = None

    def add_embeddings(self, embeddings, image_ids):
        embeddings = np.asarray(embeddings, dtype=np.float32)
        image_ids = np.asarray(image_ids, dtype=np.int64)

        if self.use_faiss and self.index is not None:
            self.index.add_with_ids(embeddings, image_ids)
        else:
            if len(self.matrix) == 0:
                self.matrix = embeddings
            else:
                self.matrix = np.vstack([self.matrix, embeddings])
            self.ids.extend(image_ids.tolist())

    def search(self, query_embedding, top_k=1):
        query = np.asarray(query_embedding, dtype=np.float32).flatten()
        if len(query) != self.dimension:
            query = np.resize(query, (self.dimension,))

        if self.use_faiss and self.index is not None:
            scores, ids = self.index.search(np.asarray([query], dtype=np.float32), top_k)
            return scores[0], ids[0]

        if len(self.ids) == 0 or len(self.matrix) == 0:
            return np.array([-1.0]), np.array([-1])

        # Cosine / Inner Product Search via NumPy
        dots = np.dot(self.matrix, query)
        k = min(top_k, len(dots))
        top_indices = np.argsort(dots)[::-1][:k]

        scores = dots[top_indices]
        ret_ids = np.array([self.ids[i] for i in top_indices], dtype=np.int64)
        return scores, ret_ids

    def save(self, path):
        if self.use_faiss and self.index is not None:
            faiss.write_index(self.index, str(path))
        else:
            np.savez(str(path) + ".npz", matrix=self.matrix, ids=np.array(self.ids, dtype=np.int64))

    def load(self, path):
        str_path = str(path)
        if self.use_faiss:
            try:
                self.index = faiss.read_index(str_path)
                return
            except Exception:
                pass

        npz_path = str_path + ".npz" if not str_path.endswith(".npz") else str_path
        if os.path.exists(npz_path):
            data = np.load(npz_path)
            self.matrix = data["matrix"]
            self.ids = data["ids"].tolist()
            self.use_faiss = False

    def count(self):
        if self.use_faiss and self.index is not None:
            return self.index.ntotal
        return len(self.ids)

    def get_dimension(self):
        if self.use_faiss and self.index is not None:
            return self.index.d
        return self.dimension