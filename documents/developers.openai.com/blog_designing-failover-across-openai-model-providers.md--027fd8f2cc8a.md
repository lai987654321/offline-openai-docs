# Designing failover across OpenAI model providers

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

When a business depends on an AI workflow, even a short provider outage can delay decisions or interrupt services. We’ve been working with financial services customers building agentic applications and cybersecurity workflows with OpenAI models. This post explains how we approach production routing and recovery for critical workloads, using a read-only fraud assessment in a payments workflow as a running example.

Here, first-party **(1P)** means the direct OpenAI API; third-party **(3P)** means OpenAI models accessed through a cloud provider, regardless of where the application runs. We’ll cover the value of direct access for preview models and features, how workload needs and private connectivity shape route choice, and which operations can safely fail over. We’ll then provide a Codex prompt for implementing the policy in an existing gateway and explain what to validate before enabling failover.

## Why use both routes?

Direct OpenAI access is valuable even when production runs through a cloud provider. A central reason is access to preview models and features: when those capabilities are available through the direct API, eligible teams can evaluate them against their own workflows before their chosen cloud provider supports them.

Where the workflow runs often shapes the production route. A third-party cloud service may fit the application’s existing infrastructure and operating controls, while direct OpenAI access may better fit another workflow’s requirements. Validate the required models, features, and behavior on your chosen route, and use direct OpenAI access for continued experimentation. What’s available depends on the provider, endpoint, region, and your account.

For critical workloads, we also consider validated failover between 1P and 3P. Provider failover means retrying a request through another approved provider when the primary cannot serve it. It helps only when the request can be repeated safely and the alternative meets the workflow’s requirements.

A global payments provider might use the [Responses API](/api/docs/guides/migrate-to-responses) for a self-contained, read-only fraud assessment. If the call times out before its result is used, the application may retry it through a validated secondary within the transaction’s deadline.

An ongoing [Agents API](/api/docs/guides/agents-api/overview) session needs a different recovery approach. Switching providers does not by itself resume its conversation and saved work or reconcile prior actions. That recovery is substantially harder and outside this post’s scope.

That distinction is why we treat multi-provider support as a platform capability and failover as a workflow decision.

## Planned routing and failover

Choosing a production route and approving failover are separate decisions. Planned routing may include splitting traffic across providers or sending excess demand to another route. These patterns need their own capacity, cost, quality, and recovery tests.

We’re seeing some customers use the [Decisions API](/api/docs/guides/decisions) as an optional input for routing. To keep the workflow resilient, define how routing behaves if that service is unavailable.

The diagrams use 1P as primary and an approved 3P route as secondary. Either can be primary, depending on the workload.

## Where the router fits



> Illustration: An AI application sends requests to a platform-operated router under workflow-defined policy. Normal traffic goes to the primary OpenAI API, while only eligible recovery traffic goes to an approved third-party provider. When no route is eligible, the workflow queues, degrades, hands off, or rejects the request. The application owns recovery context, action reconciliation, checkpoints, and duplicate-action protection.



_Figure 1. OpenAI API primary; approved third-party secondary. The platform operates the router; the application defines the policy. Models, features, capacity, controls, and availability may differ._

You can use your existing model router or LLM gateway if it can enforce separate rules for each route. Send normal traffic to the primary. Use the tested secondary only when the failover conditions are met.

Define who can use each route, in which regions, and with which models and APIs. Record the approved legal entities, teams, provider accounts or projects, and data-handling rules. Approval applies only to the agreed workloads and regions.

## Private connectivity and route choice

Many customers in regulated industries require private connectivity as part of their security controls. For those customers, choosing a route also means checking how their application’s cloud can connect privately to each provider. The diagram shows an application and gateway in a customer private network, with separate private paths to each provider.



> Illustration: An AI application and LLM gateway run inside the customer private network. The primary uses a separate private connection to the OpenAI API, with cross-cloud connectivity if required. Eligible recovery traffic uses a provider-specific private connection to an approved third-party provider. OpenAI and the secondary provider operate separate services. Public HTTPS is a separate option and does not activate automatically.



_Figure 2. OpenAI API (1P) primary; approved provider (3P) secondary, such as Amazon Bedrock or Azure OpenAI. Only eligible recovery traffic uses the secondary._

At the time of publishing, the private-connectivity options differ between 1P and 3P. For direct OpenAI access (1P), [OpenAI Private Link](/api/docs/guides/private-link) uses an Azure Private Endpoint. Workloads in AWS and Google Cloud need customer-managed connectivity into Azure to use this private path to the direct OpenAI API.

For third-party access (3P), [Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/vpc-interface-endpoints.html) uses API-specific interface VPC endpoints through AWS PrivateLink, while [Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-services/cognitive-services-virtual-networks#use-private-endpoints) uses Azure private endpoints. Before enabling failover, verify DNS, access, and regional model and API support on both routes. [OpenAI Private Link](/api/docs/guides/private-link#does-private-link-fail-over-between-regions-automatically) does not automatically switch between regional endpoints, so regional recovery needs separate configuration and testing. Any recovery to public HTTPS also requires explicit approval.

Provider support can change. Please check the official documentation before choosing or enabling a route.

## Which operations can fail over?

Not every operation has a suitable secondary route. For example:

- **Missing capabilities:** A workflow might use web search through the direct OpenAI API to check current information. If the secondary route does not support that capability, do not silently skip the search. Validate an alternative implementation or leave failover disabled for that operation.
- **Unvalidated behavior:** A matching model name or compatible API is not enough. Run the workflow’s existing harness and evaluations against the secondary before enabling it.
- **Residency or state constraints:** Do not switch to a destination that breaches approved data-location requirements or cannot access the state needed to complete the operation safely.

When no secondary qualifies, queue work within an agreed deadline, use an approved reduced-functionality or manual path, or stop safely. A retryable inference step may qualify even when the full workflow does not.

A read-only fraud assessment that times out may qualify for another attempt if its result is unused and enough time remains. Once output reaches another system, recovery needs a tested restart path. If an action may already have completed, confirm its outcome and prevent duplicate actions before restarting.

## When and how to fail over

In the payments example, a busy or unavailable model could be replaced with another approved model: model fallback. Retrying the assessment through another provider is provider failover. Sometimes both change.

We first ask whether switching providers would help. A shared gateway, retrieval service, or identity system can affect both routes. Test the secondary’s connectivity, access, and capacity, and check regional recovery support for your models, hosted tools, and data-location requirements.

If failures or slow responses persist, a circuit breaker can pause new requests to the affected route. Set error and response-time limits by provider, model, region, and workflow. Each request still needs to qualify for failover.

Before retrying a request, check that it is safe to repeat and can finish within the workflow’s deadline. The secondary must be approved, enabled, healthy, and tested for the extra load, with budget remaining. Consult OpenAI’s [error-code](/api/docs/guides/error-codes) and [rate-limit documentation](/api/docs/guides/rate-limits); check other providers’ error, retry, quota, and billing rules too.

The table below gives a conservative starting point for automatic failover. Use each provider’s error details, not just the HTTP status.

| Condition                                                        | Routing decision                                                                                                                                                                                                           |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Transient service or connection failure                          | **Consider failover** for retryable provider errors, connection resets, or timeouts.                                                                                                                                       |
| Sustained throttling or slow responses                           | **Consider failover** if waiting would breach the request or workflow deadline. Distinguish temporary throttling from quota or billing problems that need remediation.                                                     |
| Invalid request, access failure, refusal, or exhausted allowance | **Do not automatically switch routes** for malformed requests, 401/403 errors, safety refusals, exhausted quota, credits, or spend limits. Correct or escalate the cause. Unclassified errors should not trigger failover. |
| Partial output or uncertain tool action                          | **Do not blindly replay** or assume a partial response can continue on another route. Reconcile action outcomes and prevent duplicate writes before restarting.                                                            |
| Model-specific unavailability or capacity constraint             | **Try another approved model** that meets quality, feature, and latency requirements. If the provider’s shared serving path is affected, **consider the provider failover** under the prerequisites above.                 |

One layer should control retries across the application, SDK, and gateway so they do not multiply. Use a shared retry budget and follow valid [Retry-After guidance](/api/docs/guides/rate-limits). Otherwise, use [bounded exponential backoff with jitter](/api/docs/guides/rate-limits#retrying-with-exponential-backoff): wait longer between attempts, add randomness, and limit attempts. Retry only safe inference calls, within both the request and workflow deadlines.

Limit failover traffic so the secondary is not overwhelmed. Restore the primary gradually after representative requests meet error and response-time limits for a defined period. Pause the increase if those limits are exceeded. If both routes are constrained, follow the workflow’s agreed recovery policy.

## Implement the failover policy with Codex

We can now use Codex to turn those recovery rules into changes to an existing LLM gateway. For the payments example, we limit the work to the self-contained, read-only fraud-assessment step. The primary route stays in place, and failover remains disabled until the secondary is approved and validated.

Open the repository that owns the gateway configuration or application routing in Codex, then adapt the prompt below to your workflow and intended routes.

```text
Add disabled-by-default provider failover for [workflow’s self-contained, read-only inference step] in [repository/gateway]. Preserve the primary route and reuse the existing gateway, approved platform routes, and workflow policy.

Inspect gateway, SDK, and adapter versions, deployment configuration, APIs, and current official documentation. Separate app and gateway changes by owner and required review. Provide configuration and integration tests for dependencies owned elsewhere. Flag unsupported controls. Do not guess approvals or limits; keep dependent failover paths disabled until verified.

Use tested provider-specific error mappings. Allow transient service/network failures and confirmed temporary throttling only when replay is safe and the approved, enabled, healthy secondary has required features, data controls, tested capacity, remaining budget, and time to finish. Block invalid requests, access failures, refusals, exhausted quota/credits/budget, unknown errors, and ambiguous 429s.

Use one retry controller across client, gateway, and SDK. Disable conflicting retry/failover chains; enforce one total attempt limit and both request and workflow deadlines. Use configured per-attempt timeouts within the overall deadline. Accept only one result per logical request and ignore late responses from earlier attempts. Respect valid Retry-After; otherwise use bounded exponential backoff with jitter. Never blindly replay partial output or uncertain actions, or assume provider state transfers. Apply the approved queue, reduced-result, or stop policy. Include manual disable, circuit breaking, and gradual failback.

Test the actual request path with local HTTP stubs and external networking blocked. Assert route order, call counts, and elapsed time for success, eligible failures, each blocked error class, failed eligibility, partial output, uncertain actions, exhausted budgets, both routes failing, and recovery controls. Blocked cases must make no secondary call. Keep synthetic limits in test fixtures and protect secrets. Make no live calls or deployments without authorization.

Return minimal patches, tests mapped to requirements, results, rollback instructions, and outstanding live checks. Leave all unverified failover paths disabled.
```

The prompt asks Codex for a focused gateway change, tests showing when the secondary should and should not be called, and a list of checks still needed on the real routes. Review the patch and local test results first. Then validate model behavior, data controls, capacity, and recovery under load before enabling failover.

## Validate routes and recovery

The payments example illustrates checks that apply to other critical workloads too. Test both routes against the [workflow’s acceptance criteria](/api/docs/guides/evaluation-best-practices#design-your-eval-process) for quality, safety, output format, tool use, and context limits. Record the tested configuration, availability, and access requirements—including processing tiers and hosted features—and define when to retest.

The assessment’s data restrictions, including prompt and output logging limits, apply during normal operation and recovery. Before enabling either route, review credentials, network paths, retrieval, tools, stored state, and logs with legal, privacy, security, and data-governance owners.

That review needs service documentation and contracts to confirm where data is processed and stored, how long it is kept, how it is encrypted, and who controls keys and access. An endpoint’s location or a private connection alone is not enough. Controls, eligibility, and responsibilities vary by endpoint—see [OpenAI’s data controls](/api/docs/guides/your-data).

A suitable route still needs room for recovery traffic. A provider-wide dashboard can hide throttling on the fraud-assessment model, so track request and token rates, concurrent requests, throttling, response times, and remaining approved budget for each route’s model, account or project, and region.

To see whether the secondary can cope, load-test its existing work together with expected fraud-assessment traffic and retries. Use those results to set the failover traffic limit and decide which requests can wait, use reduced functionality, or stop. Quota alone does not guarantee completion before the deadline.

Moving the assessment can also change its cost and response time. Compare cost per successful assessment, including cache misses, data-transfer charges, and connectivity costs. Measure added delays from cache misses or requests crossing clouds, too.

Finally, test the failure scenarios in the table under load, plus missing features and a busy or unavailable secondary. Check that the recovery policy works as intended, including traffic limits, manual stop, and gradual return to the primary.

Assess recovery by how quickly service returns, how many assessments finish before the deadline, result quality, cost, and duplicate actions. Regular exercises keep these checks current as credentials expire, configurations change, or capacity shifts.

## Who owns recovery

One practical model is to separate ownership of the routing service from ownership of the application. A platform team could run provider integrations, the router, monitoring, and audit logs. It would own the routing service’s production readiness and enforce destination, identity, data, traffic, and spend controls, with named on-call owners to disable routes and manage the return to the primary.

In this model, application owners define which operations can fail over, the service and quality targets, and acceptable reduced functionality. They also own business outcomes, saved recovery context, tool permissions, response checks, and protection against duplicate actions, including when state or tools are shared.

Your team may combine these roles or divide them differently. Before enabling failover, agree who approves the controls, owns route testing and runbooks, and has authority to act during an incident.

## Conclusion

Consider direct OpenAI access as part of your toolbox, even when production runs through a cloud provider. It gives eligible teams a way to evaluate preview models and features, and a potential recovery route for critical workloads. Choose 1P or 3P for production based on the workflow’s capabilities, hosting environment, and controls—including private connectivity where required.

For critical workloads, start with one self-contained, read-only inference step. Codex can help implement its gateway policy and local tests, while validation on the actual routes establishes whether the secondary meets the workflow’s requirements. That gives the team a concrete recovery plan: when to switch, when to stop, and who owns the decision.