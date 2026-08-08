from tqdm.auto import tqdm

def compute_relevance(q, search_function):
    record_id = q["record_id"]
    herb_id = q["herb_id"]
    record_type = q["record_type"]
    results = search_function(query=q["question"])

    relevance = []
    for d in results:
        relevance.append(int(d["record_id"] == record_id and d["herb_id"] == herb_id and d["record_type"] == record_type))

    return relevance

def compute_relevance_total(ground_truth, search_function):
    relevance_total = []

    for q in tqdm(ground_truth):
        relevance = compute_relevance(q, search_function)
        relevance_total.append(relevance)

    return relevance_total

def hit_rate(relevance):
    cnt = 0

    for line in relevance:
        if 1 in line:
            cnt = cnt + 1

    return cnt / len(relevance)

def mrr(relevance):
    total_score = 0.0

    for line in relevance:
        for rank in range(len(line)):
            if line[rank] == 1:
                total_score = total_score + 1 / (rank + 1)
                break

    return total_score / len(relevance)

def evaluate(ground_truth, search_function):
    relevance_total = compute_relevance_total(ground_truth, search_function)

    return {
        "hit_rate": hit_rate(relevance_total),
        "mrr": mrr(relevance_total),
    }