# Maintaining software with the GPT-6 family

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Every growing codebase needs maintenance: unused code to remove, completed experiments to clean up, and tests to fix. At OpenAI, coding agents have helped us build faster, which has also increased our maintenance needs.

I work on OpenAI’s Core Experimentation team, where we build and maintain the software that supports experiments across the company, from front-end updates to improvements in model-serving efficiency.

The release of GPT-6 Astra helped us build and maintain software faster, and GPT-6.1 Sol delivered similar results at a lower cost. In this post, I’ll share how we use these models to find cleanup opportunities, gather evidence, and prepare changes for review.

## Removing unused code

Before agentic coding, many software engineering teams relied on complex static analysis systems integrated with runtime logging to detect and remove unused code. Even with these systems and careful code reviews, mistakes happen. I recall several incidents due to mistaken code removal. There are too many edge cases to consider, like reflection throwing off static analysis or an unused code path that can be activated to mitigate future incidents.

With GPT-5.6 Sol in Codex, I could specify an area to investigate and clear validation criteria, then let the model write static analysis and remove dead code. These targeted prompts were easier to develop and maintain than our existing static analysis systems, with similar reliability.

When we got access to GPT-6 Astra, we wanted to see whether it could work from a broader request, figuring out where to look and what evidence it needed to justify each removal. We started with a short Codex prompt that was too ambiguous for GPT-5.6 Sol to handle completely. Here it is, typos and all:



**Prompt:**

```text
Can you help identify and clean up dead code in the repo please, feel free to check slack,
statsig [a feature flag and experimentation platform we use], or any other source you need to
confirm that things are indeed no longer being used and can be cleaned up or simplified
```

GPT-6 Astra

Astra handled the ambiguity well. It looked at past PRs, gathered context from Slack threads, and inspected internal project trackers. It read production performance profiling tables to confirm the deleted lines were never reached. Astra also explained its rationale for each deletion, which accelerated our reviews.

Once we saw how well Astra was doing, five engineers collaborated to run variations of that prompt across repositories, and we merged more than 1,400 pull requests, deleting over 800k lines of code. We did the bulk of this part-time over two weeks while primarily working on other projects. Code reviews were fanned out to various teams with context on each affected project. These deletions resulted in measurable benefits. For example, one service’s container image shrank from 3.31GB to 1.72GB, a 48% reduction, and another set of cleanups removed about 400 visual snapshot variants from our test suite.

## Tracking down stale experiments

A harder problem in software maintenance is cleaning up _stale_ experiments. These experiments aren’t necessarily unused: their code might still run in production or depend on eligibility evaluations that could change at any time, making static analysis much harder. Historically, our team cleaned up stale experiments through deterministic static analysis augmented with database queries and used our most powerful model (then GPT-5.6 Sol) to build and improve the associated scripts. We knew this resulted in many false negatives where our analysis couldn’t identify truly stale experiments.

Given our success with dead code cleanup using GPT-6 Astra, I decided to try another short prompt for stale experiments. I wasn’t sure how to get started, so I brainstormed with Astra and asked it to write a short prompt to try in a new thread:



**Prompt:**

```text
Find and remove substantial dead code associated with stale, constant Statsig gates/configs or
abandoned experiments in projects {A} and {B}. Verify live Statsig configuration and check git
history and overlapping PRs. Preserve production behavior, operational safeguards and
gates/configs intended as killswitches or similar. Ignore SDK fallbacks and local overrides.
Create one small draft PR per cleanup, linking its Statsig configuration console link in the
summary.
```

GPT-6 Astra

Astra followed the safeguards in the prompt and prepared changes with evidence our team could review. I commented on its pull requests, then asked Astra to look at my comments, incorporate my feedback, and develop a new prompt to scan our entire codebase. I was afraid of having too many things to clean up and no way to prioritize them, so I also asked Astra to help me with that. Astra suggested this prompt:



**Prompt:**

```text
/goal Find every stale, constant, abandoned, or fully shipped Statsig gate, config, experiment,
and layer present in this entire repository that can safely be removed with no production
changes. Audit all Statsig projects and inventories, not just objects labeled stale.
Find indirect usages through enums, constants, wrappers, aliases, schemas, dynamically assembled
names, and cross-service consumers. Reconcile every production-referenced constant; do not stop
after producing a conservative shortlist.
Consider each object's cloud resource usage, including CPU. Use production telemetry and
profiles where available to identify expensive dead checks.
[Omitted for brevity: detailed instructions, generated by Astra, on verifying production
behavior, prioritizing older objects, preserving intentional safeguards, and interpreting SDK
fallbacks.]
Produce a markdown report grouping all verified candidates into parallelizable ownership/file
workstreams, including production values, evidence, owners, callsites, and observed evaluation
or CPU costs if available.
Do not modify live configurations or services.
```

GPT-6 Astra

The resulting report was promising. Using our instrumentation, Astra investigated the CPU costs of each stale experiment, and the top few results were large efficiency wins associated with experiments that no one had identified as stale for years. I carefully validated those larger results and proceeded with the full cleanup, which removed hundreds of experiments and feature flags.

One example shows Astra’s judgment: several years ago, one of our engineers created a [Statsig](https://www.statsig.com/) feature flag that allowed internal developers to override all our other feature flags related to new features, for testing purposes. This configuration was implemented through a single line of Python code that mapped the flag to all other features. That line lived alongside hundreds of similar feature flag mappings and looked inconspicuous.

Astra found that the line above caused significant CPU fan-out because it mapped the flag to _all_ features. It investigated the CPU cost, but raised the finding for human review because the flag had been explicitly marked as “Permanent” in our feature flag management console and could still serve an operational purpose. After review, we removed the flag, with an estimated 0.42% CPU saving in the main affected service.

## Improving cost effectiveness with GPT-6.1 Sol

More recently, we tested GPT-6.1 Sol on the same workflows to see whether it could match GPT-6 Astra’s effectiveness while being more efficient.

To compare the models on stale experiment cleanup, I ran the same prompt above on different model/effort combinations, asking Codex to audit specific subdirectories in one of our repositories to find stale experiments. These subdirectories cover over 6,000 files and 1 million lines of code in Python, TypeScript, Go and Rust. I reviewed the findings to validate them. The graph below shows the results for 3 model/effort combinations:



> Illustration: Stale experiment cleanup. GPT-6 Astra Ultra: $109.06 API cost, 142 findings, $0.77 per finding. GPT-6.1 Sol Ultra: $15.12 API cost, 131 findings, $0.12 per finding. GPT-6.1 Sol Medium: $5.27 API cost, 86 findings, $0.06 per finding. Costs use standard API pricing and include research subagents and the follow-up turns Codex ran automatically while working toward each goal.



In this comparison, GPT-6.1 Sol Ultra produced 92% as many findings as GPT-6 Astra Ultra at 14% of the API cost. GPT-6.1 Sol Medium produced fewer accepted findings at a lower cost.

I reviewed the discrepancies across model/effort combinations, and a few patterns emerged. For instance, most of the discrepancies between models on Ultra were due to constant feature flags used as dependencies in other feature flags. GPT-6 Astra identified those, but GPT-6.1 Sol missed them.

Finding error patterns like this helps us develop prompts that correct for them, so the more cost-effective model can achieve results similar to those of the more expensive one. At the same time, future model releases can make these corrections obsolete, so it’s important to revisit prompts when new models are released.

## Other ideas to try

Some of my favorite Codex discoveries started with short prompts like these. Try them with GPT-6.1 Sol Medium, and consider increasing effort for broader audits if the results are promising.

Fixing flaky tests:



**Prompt:**

```text
/goal Look at all recent CI runs to find flaky tests. For each flaky test, try a fix and if
successful put up a PR. Your job is to find clear fixes to simple issues, not to exhaustively
fix every flaky test.
```

GPT-6.1 Sol · Medium

Improving agentic context:



**Prompt:**

```text
Look through my recent Codex sessions and find one AGENTS.md instruction that appears to have
misdirected an agent or caused unnecessary work. Choose the original session prompt where that
happened. Replay that same prompt twice from the same repository snapshot and model:
1. With the current AGENTS.md instruction unchanged.
2. With only that one instruction removed or fixed.

Compare task quality, agent behavior, tool calls, token usage, runtime, and cost. Show the
instruction and whether updating it helped.
```

GPT-6.1 Sol · Medium

Reducing cost and runtime of continuous integration:



**Prompt:**

```text
What ideas do you have to relieve CI load in this repository? List your ideas in a table and
rank all of them by estimated CI minutes saved per day based on this repo's CI run history
```

GPT-6.1 Sol · Medium

This last idea helped us reduce CI time. After running it and following up on the suggestions, we landed about 30 CI optimization PRs. We saw median CI completion time fall from roughly 10 minutes to 4.5 minutes, while the 90th percentile fell from 12.5 minutes to 6 minutes. In a later fix, adding a missing mock cut a 63-test resolver suite’s runtime from 592.6 seconds to 29.8 seconds—a 95% reduction, with all 63 tests retained.

## Start small, review, and expand

The GPT-6 series has improved how our Core Experimentation team maintains software at scale and unlocked several efficiency wins.

So far, my team has merged more than 1,400 maintenance pull requests that started from GPT-6 proposals. This resulted in faster test execution, smaller images, lower CPU utilization, and many other benefits. However, some proposals added more complexity than their expected benefit justified, so prioritization and measurement remained an important part of our workflow.

In larger codebases, we’ve found it easy to be overwhelmed by the number of optimizations GPT-6 models can find. With instrumentation and the prompt techniques shared above, Codex has helped us prioritize those improvements.

If you want to try this in your own codebase, I’d start with one small maintenance task: some unused code, a stale feature flag, or a flaky test. Ask Codex to find an instance, gather evidence, and propose a small draft PR. Compare different models and efforts for that small task, since a cheaper configuration may be enough.

Once a small pass works well, scale it up to a subdirectory or well-scoped project. At each step, ask Codex to incorporate your code review feedback into the next prompt. When you’re confident in the model’s performance, expand to your whole codebase.

---

Our Core Experimentation team is hiring in Engineering, Data Science, and Product Management. If this post excites you, please apply through our [careers page](https://openai.com/careers/)!