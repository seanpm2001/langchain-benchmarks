def test_import_langchain_docs() -> None:
    """Test that the langchain_docs environment can be imported."""
    from langchain_benchmarks.rag import tasks, evaluators  # noqa: F401