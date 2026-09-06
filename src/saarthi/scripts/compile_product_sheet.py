from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from saarthi.config import get_settings
from saarthi.providers.groq import GroqStructuredClient
from saarthi.services.knowledge_compiler import KnowledgeCompiler


async def compile_file(source: Path, output: Path) -> int:
    settings = get_settings()
    client = GroqStructuredClient(
        api_key=settings.groq_api_key.get_secret_value(),
        model=settings.groq_model,
        timeout_seconds=settings.groq_timeout_seconds,
        temperature=0,
    )
    try:
        facts = await KnowledgeCompiler(client).propose(
            source.read_text(encoding="utf-8"),
            product_id="SPL-DEMO-01",
            product_version="1.1",
            fact_set_version="1.1",
        )
    finally:
        await client.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "review_required": True,
                "facts": [fact.model_dump(mode="json") for fact in facts],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return len(facts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile a free-form synthetic product sheet into draft atomic facts."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    count = asyncio.run(compile_file(args.input, args.output))
    print(
        f"Created {count} draft facts for human review; none were approved or ingested."
    )


if __name__ == "__main__":
    main()
