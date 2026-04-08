[2026-03-25 11:00] The user first questioned why seju-lite does not use LangChain as the main runtime architecture and wanted a comparison between custom runtime control and framework-driven agents.

[2026-03-27 16:20] We inspected loop.py and subagent.py, focusing on how messages, final content, and background tasks are handled. The user was especially interested in where return values are formed and where concurrency is actually implemented.

[2026-03-29 08:45] The discussion shifted toward subagent evolution, including possible RQ, Celery, and LangGraph designs. The user chose to keep subagent lightweight and task-only rather than turning it into a full workflow graph.

[2026-04-01 13:10] We explored DeerFlow's source and extracted design lessons around middleware-driven short-term summarization and structured long-term memory, concluding that the ideas matter more than the LangGraph dependency itself.

[2026-04-05 19:55] The user requested an isolated v2 directory in seju-lite so the new design could be built without mutating the main path, making rollback straightforward and experimentation safer.

[2026-04-08 17:30] We added a runtime adapter and token comparison tooling, then discovered the importance of comparing modes against the same raw session history window rather than letting policy routing remove history from short greeting prompts.
