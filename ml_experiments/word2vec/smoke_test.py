"""Quick smoke test — no full training, just wiring checks."""
from word2vec.config import Word2VecConfig
from word2vec.dataset import load_corpus
from word2vec.vocabulary import Vocabulary
from word2vec.model import Word2Vec
from word2vec.evaluate import AnalogyEvaluator
import torch
import numpy as np

cfg = Word2VecConfig(min_count=2, max_vocab_size=500, embedding_dim=50)
tokens = load_corpus(None)
vocab = Vocabulary.build(tokens, cfg.min_count, cfg.max_vocab_size)
vocab.build_neg_table()
print(f"Vocab size: {vocab.size}")

model = Word2Vec(vocab.size, cfg.embedding_dim)
center = torch.tensor([vocab.encode("king")], dtype=torch.long)
ctx    = torch.tensor([vocab.encode("queen")], dtype=torch.long)
negs   = torch.tensor([vocab.sample_negatives(vocab.encode("king"), 3)], dtype=torch.long)
loss = model(center, ctx, negs)
print(f"Forward pass loss: {loss.item():.4f}")

emb = model.get_embeddings()
print(f"Embeddings shape: {emb.shape}")
norms = np.linalg.norm(emb[2:5], axis=1)
print(f"L2 norms (should be ~1.0): {norms}")

evaluator = AnalogyEvaluator(model, vocab)
print(f"Analogy pairs loaded: {len(evaluator._pairs)}, category set: {set(evaluator._categories)}")
train_p, val_p, test_p = evaluator._stratified_splits()
print(f"Splits — train:{len(train_p)}  val:{len(val_p)}  test:{len(test_p)}")

print("\nAll smoke-test checks PASSED")
