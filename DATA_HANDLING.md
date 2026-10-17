# Data handling — hosted platform tier

This document is a prerequisite for the hosted grāmatr platform service
deployment target (`INJECTION_GUARD_AUTH_TOKEN` set, fronted by a load
balancer). It does not apply to the local Docker tier, which never
sends scanned text anywhere outside the machine it runs on.

## What transits the network

Text submitted to `/classify` — the actual content being scanned for
prompt-injection/jailbreak attempts. This is typically tool output
(web pages, file contents, PR descriptions) that an agent session is
about to act on, not literal secret values (that's `secret-guard`'s
job, which has no hosted tier for exactly this reason — see its
README).

## Commitments

1. **No persistence of scanned text.** The daemon classifies and
   returns a result; it does not write the input text to disk, a
   database, or any log sink, anywhere in the request path.
2. **No logging of request bodies.** Application logs (stdout, as
   configured in `daemon.py`) must never include the `text` field from
   a `/classify` request. `uvicorn`'s access logging must not log
   request bodies — confirm this explicitly if access logging is ever
   enabled for the hosted deployment (it is not configured either way
   as of this document; this is a requirement for whoever configures
   it, not a guarantee the current code already enforces at the
   infrastructure layer).
3. **No use in model training.** Scanned text is never used to
   fine-tune, retrain, or otherwise improve any model, grāmatr's own or
   third-party.
4. **Classification results (not input text) may be logged** for
   operational metrics (e.g. "N requests, M flagged as malicious") —
   aggregate counts only, never the text that produced them.
5. **Transport security:** the hosted endpoint must be TLS-terminated
   before reaching this service — this document assumes that, it is
   not something the daemon itself implements.

## What this document is NOT

This is a design commitment, written alongside the code, not a
third-party audit, a signed DPA, or legal language reviewed by counsel.
Before this is referenced in any customer-facing claim (a security
page, a sales conversation, a compliance questionnaire answer), it
needs that review. Treat it as the engineering team's statement of
intent that a reviewer can hold the actual deployment accountable to —
not as the final word.

## Verifying compliance before the hosted tier goes live

- [ ] Confirm no log sink in the actual k8s deployment captures request
      bodies (application logs, ingress/load-balancer access logs,
      service mesh tracing — any of these could leak the text field if
      misconfigured, independent of what `daemon.py` itself does)
- [ ] Confirm TLS termination is in place end-to-end
- [ ] Legal/compliance review of this document before it's cited anywhere customer-facing
- [ ] Decide retention policy for the aggregate metrics mentioned in point 4 (how long, where stored)
