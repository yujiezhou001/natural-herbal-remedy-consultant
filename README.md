# Natural Herbal Remedy Consultant

This is a natural remedy consultant with knowledge from Chinese traditional herb bible HuangDiNeiJing, built as an RAG application for the LLM zoomcamp project

## Problem Description

Information about natural remedies is often scattered across traditional medical texts, herbal references, modern research, and safety resources. This makes it difficult to quickly answer practical questions such as what natural remedies may help with sleep, a common cold, nausea, or other everyday concerns, while also understanding their traditional uses, modern scientific evidence, preparation methods, side effects, and drug interactions.

This project addresses that problem by building a Retrieval-Augmented Generation (RAG) assistant over a curated natural-remedies dataset. A user can ask a question in natural language, and the application retrieves relevant information about herbs and remedies before providing a grounded response.

The assistant is intended for educational and research purposes and not as a replacement for professional medical diagnosis or treatment.

## Running it

we use venv for managing dependencies and Python 3.9.

Make sure you have uv installed:

```bash
pip install uv
```

Installing the dependencies:

```bash
venv install
```

## Evaluation

For the code for evaluating the system, you can check the [notebooks/notebook.ipynb](notebooks/notebook.ipynb)

### Retreival

- using minsearch without any boosting - gave the following metrics:

text {'hit_rate': 0.944, 'mrr': 0.5907800000000012}
vector {'hit_rate': 0.9172, 'mrr': 0.6094866666666657}
hybrid {'hit_rate': 0.9648, 'mrr': 0.6329333333333339}

- using minsearch and hyperopt with boosting - gave the following metrics:

text (untuned)     {'hit_rate': 0.9420833333333334, 'mrr': 0.5909375000000011}
text (boosted)     {'hit_rate': 0.9454166666666667, 'mrr': 0.6158125000000004}
vector             {'hit_rate': 0.915, 'mrr': 0.606145833333333}
hybrid (default)   {'hit_rate': 0.9633333333333334, 'mrr': 0.6305208333333339}
hybrid (tuned)     {'hit_rate': 0.9458333333333333, 'mrr': 0.6322638888888894}


### RAG Flow

For the code of RAG flow, you can check the [notebooks/consultant.py](notebooks/consultant.py) and use 'make run' command directly in the terminal.

## Monictoring

## Ingestion