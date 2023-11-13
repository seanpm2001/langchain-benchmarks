import argparse
from functools import partial
from typing import Optional, Callable

from langchain.chat_models import ChatOpenAI
from langchain.smith import RunEvalConfig, run_on_dataset
from langchain.schema.runnable import Runnable
from langsmith import Client
from chat_langchain.chain import create_full_chain
from anthropic_iterative_search.chain import chain as anthropic_agent_chain
from openai_functions_agent import agent_executor as openai_functions_agent_chain
from oai_assistant.chain import agent_executor as openai_assistant_chain

import uuid

ls_client = Client()


def _get_chain_factory(arch: str) -> Callable:
    _map = {
        "chat": create_full_chain,
        "anthropic-iterative-search": lambda _: anthropic_agent_chain,
        "openai-functions-agent": lambda _: openai_functions_agent_chain,
        "openai-assistant": lambda _: openai_assistant_chain,
    }
    return _map[arch]


def create_runnable(
    arch: str, model_config: Optional[dict], retry_config: Optional[dict] = None
):
    factory = _get_chain_factory(arch)
    chain: Runnable = factory(model_config)
    if retry_config:
        return chain.with_retry(**retry_config)
    return chain


def get_eval_config():
    accuracy_criteria = {
        "accuracy": """
Score 1: The answer is incorrect and unrelated to the question or reference document.
Score 3: The answer shows slight relevance to the question or reference document but is largely incorrect.
Score 5: The answer is partially correct but has significant errors or omissions.
Score 7: The answer is mostly correct with minor errors or omissions, and aligns with the reference document.
Score 10: The answer is correct, complete, and perfectly aligns with the reference document.

If the reference answer contains multiple alternatives, the predicted answer must only match one of the alternatives to be considered correct.
If the predicted answer contains additional helpful and accurate information that is not present in the reference answer, it should still be considered correct.
"""  # noqa
    }

    eval_llm = ChatOpenAI(model="gpt-4", temperature=0.0)
    return RunEvalConfig(
        evaluators=[
            RunEvalConfig.LabeledScoreString(
                criteria=accuracy_criteria, llm=eval_llm, normalize_by=10.0
            ),
            # Mainly to compare with the above
            # Suspected to be less reliable.
            RunEvalConfig.EmbeddingDistance(),
        ]
    )


def main(
    # server_url: str,
    arch: str,
    dataset_name: str,
    model_config: Optional[dict] = None,
    max_concurrency: int = 5,
    project_name: Optional[str] = None,
    retry_config: Optional[dict] = None,
):
    eval_config = get_eval_config()
    project_name = project_name or arch
    project_name += uuid.uuid4().hex[:4]
    run_on_dataset(
        client=ls_client,
        dataset_name=dataset_name,
        llm_or_chain_factory=partial(
            create_runnable, arch, model_config=model_config, retry_config=retry_config
        ),
        evaluation=eval_config,
        concurrency_level=max_concurrency,
        project_name=project_name,
        project_metadata={"arch": arch, "model_config": model_config},
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str)
    parser.add_argument("--dataset-name", type=str, default="Chat Langchain Pub")
    parser.add_argument("--project-name", type=Optional[str], default=None)
    parser.add_argument("--max-concurrency", type=int, default=5)
    args = parser.parse_args()
    main(
        args.url,
        args.dataset_name,
        max_concurrency=args.max_concurrency,
        project_name=args.project_name,
    )