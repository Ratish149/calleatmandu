import json
import sys

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from message.services.ai_reply_service import AIReplyService
from message.services.ai_tools import execute_tool, get_enabled_tool_schemas
from message.services.ollama_service import OllamaError, OllamaService
from message.services.reply_quality import REPRESENTATIVE_CASES, assess_reply


class Command(BaseCommand):
    help = (
        "Run representative customer questions through the live Ollama model and "
        "print the replies with basic quality metrics (naturalness, language "
        "consistency, conciseness). Requires OLLAMA_KEY to be set."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--runs",
            type=int,
            default=1,
            help="Number of times to run each case (default: 1).",
        )
        parser.add_argument(
            "--model",
            type=str,
            default=None,
            help="Override OLLAMA_MODEL for this evaluation run.",
        )
        parser.add_argument(
            "--no-tools",
            action="store_true",
            help="Skip tool calls (faster, but replies cannot use real business data).",
        )
        parser.add_argument(
            "--branch-id",
            type=str,
            default=None,
            help="Branch primary key to load branch info for the system prompt.",
        )

    def handle(self, *args, **options):
        # Model output can contain non-cp1252 Unicode (e.g. narrow no-break
        # spaces); keep printing from crashing the console on Windows.
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass

        if not getattr(settings, "OLLAMA_KEY", ""):
            raise CommandError(
                "OLLAMA_KEY is not set. Configure it before running live evaluation."
            )

        runs = max(1, options["runs"])
        model = options.get("model")
        no_tools = options.get("no_tools")
        branch_id = options.get("branch_id")

        system_prompt = AIReplyService._build_system_prompt(
            branch_id, language_hint="romanized"
        )

        for input_text, category in REPRESENTATIVE_CASES:
            for run_index in range(runs):
                reply = self._generate(
                    system_prompt, input_text, model, no_tools, branch_id
                )
                metrics = assess_reply(reply, language="romanized")
                self.stdout.write(
                    self.style.MIGRATE_HEADING(f"[{category}] {input_text}")
                )
                self.stdout.write(f"  reply: {reply or '<empty>'}")
                self.stdout.write(f"  metrics: {json.dumps(metrics, sort_keys=True)}")
                if run_index < runs - 1:
                    self.stdout.write("")

    def _generate(self, system_prompt, input_text, model, no_tools, branch_id):
        service = OllamaService(model=model)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_text},
        ]
        try:
            if no_tools:
                response = service.chat(messages)
                message = response.get("message") or {}
                return (message.get("content") or "").strip()
            return service.generate_with_tools(
                messages=messages,
                tools=get_enabled_tool_schemas(),
                execute_tool=lambda name, arguments: execute_tool(
                    name, arguments, branch_id=branch_id
                ),
            )
        except OllamaError as exc:
            self.stderr.write(self.style.ERROR(f"  Ollama error: {exc}"))
            return ""
