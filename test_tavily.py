from utils.tavily_search import search_docs

results = search_docs(
    "FastAPI JWT Authentication latest documentation"
)

for i, result in enumerate(results, start=1):
    print(f"\nResult {i}")
    print("Title:", result["title"])
    print("URL:", result["url"])
    print("Content:", result["content"][:300], "...")