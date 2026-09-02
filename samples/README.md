# Sample PDFs

Three papers from arXiv, included so the project can be run and evaluated without hunting for a corpus first.

| File | Paper | arXiv | Pages |
|---|---|---|---|
| `attention-is-all-you-need.pdf` | Attention Is All You Need | [1706.03762](https://arxiv.org/abs/1706.03762) | 15 |
| `bert.pdf` | BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding | [1810.04805](https://arxiv.org/abs/1810.04805) | 16 |
| `retrieval-augmented-generation.pdf` | Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | [2005.11401](https://arxiv.org/abs/2005.11401) | 19 |

Each is the author-submitted PDF as published on arXiv, unmodified. They are here for evaluation and are not part of the deliverable — the rights stay with their authors, and the "Attention Is All You Need" PDF carries its own reproduction notice from Google on page 1.

They were chosen for reasons the retrieval actually exercises. They overlap heavily in vocabulary, so a question about one can plausibly retrieve from another and a lazy retriever gets caught. They are dense with numbers and named configurations — `8` attention heads, `15%` masking, `BERT-base` versus `BERT-large` — which is what the keyword half of the search is for, since an embedding treats those as almost interchangeable. And they cite each other, so a question phrased in one paper's language often has its answer in another's.

`eval/questions.yaml` scores against exactly these three files by name, so replacing them means rewriting the expected pages there too.
