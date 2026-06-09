# Project 1: Customer Support Agent
## Architecture Document
This is the document that defines our architecture

## What This System Does
This is an application to suport the agentic workflow for:
Exam TS 1.1: Design and implement agentic loops for autonomous task execution  
Exam TS 1.4: Implement multi-step workflows with enforcement and handoff patterns 
Exam TS 1.5: Apply Agent SDK hooks for tool call interception and data normalization
It will implement a flow that will work with a customer and make sure a refund is processed


## System Flow
The flow for the system will be:
1. Ask the Customer a question (we will focus on process refunds)
2. Obtain the Customer (We must get the exact customer before moving forward)
3. Get the Order number (We must get the order number before moving forward)
4. Execute Refund (We must get confirmation that the Refund was executed)
5. If any of the steps above can not be executed, or if this is not a process refund, then Get a Human in the loop

## The Agentic Loop
The loop works as follows:
1. Customer message is sent to Claude along with all four tools
2. Claude decides what to do next and responds
3. We check stop_reason:
   - stop_reason = "tool_use" → Claude wants to call a tool
        → we execute that tool against the database
        → we send the result back to Claude
        → go back to step 2
   - stop_reason = "end_turn" → Claude is finished
        → return Claude's response to customer
        → stop the loop

The loop NEVER terminates based on Claude's words.
Only stop_reason drives termination — this is deterministic.

Claude decides which tools to call and in what order.
We just execute what Claude requests and return the results.

If the loop runs more than 10 iterations without resolving
we escalate to human — something is wrong.

## Tools
### get_customer
**Purpose:** Uniquely identify and verify the customer 
before any other action can be taken.

**Input:** Email address only

**Why email:** Email is unique per customer. Name and address 
can match multiple customers. Phone numbers change. 
Email is the most reliable single identifier.

**Limitation:** Customer must know the email on their account.
If they don't know it — escalate to human.

**Output:**
- Customer ID
- Full name
- Email
- Account status (active/suspended)
- Customer tier (standard/VIP)

**Business rules:**
- Look up customer by email in the database
- Customer must be verified before any other tool can run
- Suspended accounts cannot process refunds — escalate immediately
- Maximum 2 verification attempts before escalating to human

**Error cases:**
- Email not found → ask customer to verify email, max 2 attempts
- Account suspended → escalate to human immediately
- Email format invalid → ask customer to re-enter


### lookup_order
**Purpose:** Find and verify the specific order before  a refund can be processed.

**Input:** 
- Customer ID (must come from get_customer — required)
- Order number (e.g. #12345)

**Why order number:** Order numbers are unique identifiers  that customers receive in confirmation emails. 
More reliable than descriptions which can be vague or misremembered.

**Limitation:** Customer must know their order number. If they don't know it — we can list their recent orders 
to help them identify the right one.

**Output:**
- Order ID
- Order number
- Items ordered
- Order date
- Order status (processing/shipped/delivered/returned)
- Order total amount
- Delivery date

**Business rules:**
- Customer ID must be verified before this tool can run
- Order must belong to the verified customer — never return 
  another customer's order
- Maximum 2 attempts to find the correct order before escalating

**Error cases:**
- Order number not found → ask customer to verify, max 2 attempts
- Order belongs to different customer → escalate immediately
- Customer has no orders → escalate to human

### process_refund
**Purpose:** Process a refund for a verified customer 
and verified order.

**Input:**
- Customer ID (must come from get_customer — required)
- Order ID (must come from lookup_order — required)
- Refund amount
- Reason for refund

**Why both IDs:** Customer ID + Order ID together verify 
the order belongs to that customer. Prevents refunding 
the wrong customer's order.

**Output:**
- If approved: confirmation number, amount refunded, 
  timeline (3-5 business days), payment method refunded to
- If pending: escalation ticket number, explanation that 
  manager approval is required, estimated response time
- If failed: reason for failure, escalation to human

**Business rules:**
- Customer ID must be verified before this tool can run (enforced by PreToolUse hook)
- Order ID must be verified before this tool can run (enforced by PreToolUse hook)
- Refunds of $500 or less → process automatically
- Refunds over $500 → PreToolUse hook blocks the call *before* it runs
  and returns an error to Claude (requires_escalation), so Claude escalates
- Order must have status "delivered" to be eligible (enforced inside the tool)
- Orders already refunded → cannot refund again (enforced inside the tool)
- Wait for database confirmation before telling customer
- Never tell customer refund is complete until database confirms

**Error cases:**
- Refund over $500 → PreToolUse hook blocks; refund never executes, Claude escalates
- Order not "delivered" → tool returns not-eligible error, explain policy, escalate if disputed
- Order already refunded → tool returns error, tell customer, escalate if disputed
- Order not found for this customer → tool returns error (requires_escalation)


### escalate_to_human
**Purpose:** Send the full conversation to a human for assistance.  The human will then take the steps to manually resolve

**Input:**
- Customer Number: If available
- Order Number: If available
- Reason why escalating
- The full message context of what has gone on so far.

**When Does it Fire:**
1. Orders over $500
2. When Customer Number can not be obtained
3. When Invoice Number can not be obtained
4. When the User asked a question outside of Rules
5. Customer asks for Human
6. Refund Fails

**Output:**
- Message to customer: "I'm connecting you with a human agent 
  who can help. Please hold — estimated wait time is X minutes."
- Escalation ticket number — customer can reference this
- Summary of what was tried so far
- Reason for escalation (for the human agent, not the customer)
- Recommended next action for the human agent

### Hooks
We run three hooks. Two are PreToolUse (they can block a call before it
runs); one is PostToolUse (it observes the result after the fact).

**Hook 1 — PreToolUse on lookup_order** (`hook_pre_lookup_order`)
Two checks, both must pass or the call is blocked:
If no verified customer ID:
    Block lookup_order
    Return error to Claude: "Must verify customer identity first"
If the customer_id Claude passed does not match the verified customer ID:
    Block lookup_order
    Return error to Claude: "Customer ID mismatch — use the verified ID"
Otherwise allow the call.

**Why a hook and not a prompt instruction:**
The system prompt could say "never move forward without a verified
customer ID" but Claude is probabilistic — it usually follows
instructions but not always. One mistake means we surface the wrong
customer's orders. The hook verifies in code — deterministic, no
exceptions, no hallucinations possible.

**Hook 2 — PreToolUse on process_refund** (`hook_pre_process_refund`)
Three checks, evaluated in order; the first failure blocks the call:
If no verified customer ID:
    Block — "Must verify customer identity first"
If no verified order ID:
    Block — "Must verify order first"
If refund amount > $500:
    Block — error with requires_escalation=True
    (the refund never executes; Claude escalates to a human)
Otherwise allow the call.

Note: the $500 enforcement lives HERE, in the PreToolUse hook — not in
PostToolUse. Blocking before execution means no money ever moves on an
over-threshold refund, even briefly.

**Why a hook and not a prompt instruction:**
The system prompt could say "never refund over $500 / never move forward
without customer and order IDs" but Claude is probabilistic. One mistake
means real money goes to the wrong place or the wrong order is refunded.
The hook checks the amount and prerequisites in code — deterministic, no
exceptions, no hallucinations possible.

**Hook 3 — PostToolUse on process_refund** (`hook_post_process_refund`)
Fires only after a refund that was allowed through (i.e. ≤ $500 and all
prerequisites met). It does not block anything — it logs the successful
refund (amount + confirmation number) for the audit trail and returns the
tool result unchanged. The $500 threshold check used to live here; it
moved to Hook 2 so over-threshold refunds never reach execution.

**Key principle:**
Prompt instructions tell Claude what to do.
Hooks make it impossible to do the wrong thing.
Use a PreToolUse hook when a mistake has real consequences (block before
it happens); use a PostToolUse hook to observe/normalize what did happen.

Note: refund *eligibility* checks that are not security prerequisites —
order must be "delivered", and not already refunded — are enforced inside
the process_refund tool itself, not in a hook.

**Key principle:**
Prompt instructions tell Claude what to do.
Hooks make it impossible to do the wrong thing.
Use hooks for any rule where a mistake has real consequences.

## Escalation Decision Tree

Start: Customer sends a message
         ↓
Is this a refund request?
    NO  → "I can only help with refunds" → END
    YES → continue
         ↓
Can we verify the customer? (max 2 attempts)
    NO  → escalate_to_human (reason: cannot verify customer)
    YES → continue
         ↓
Can we find the order? (max 2 attempts)
    NO  → escalate_to_human (reason: order not found)
    YES → continue
         ↓
Is refund amount over $500?
    YES → PreToolUse hook blocks process_refund
        → escalate_to_human (reason: requires manager approval)
    NO  → continue
         ↓
Is the order eligible? (status "delivered" AND not already refunded)
    NO  → process_refund returns not-eligible error
        → explain policy, escalate if disputed
    YES → continue
         ↓
Did refund process successfully?
    NO  → escalate_to_human (reason: processing failed)
    YES → confirm to customer → END

At any point:
    Customer asks for human → escalate_to_human immediately
    Loop exceeds 10 iterations → escalate_to_human

## What This Does NOT Do
- Does not handle requests other than refunds
- Does not handle general customer questions
- Does not handle account changes or updates
- Does not handle shipping inquiries
- Does not handle product questions

**Why:** Narrow scope allows deep implementation of all 
agentic patterns — hooks, prerequisites, escalation — 
without complexity from multiple request types. 
Scope can expand in future versions.


## Database

### customers table
- customer_id (primary key)
- email (unique)
- full_name
- account_status (active/suspended)
- customer_tier (standard/VIP)
- created_at

### orders table
- order_id (primary key)
- customer_id (foreign key → customers)
- order_number (unique, e.g. #12345)
- items (JSON — list of items ordered)
- order_date
- delivery_date
- order_status (processing/shipped/delivered/returned)
- total_amount
- already_refunded (boolean)

### refunds table
- refund_id (primary key)
- order_id (foreign key → orders)
- customer_id (foreign key → customers)
- refund_amount
- reason
- status (approved/pending/failed)
- confirmation_number
- created_at

### escalations table
- escalation_id (primary key)
- customer_id (foreign key → customers, nullable)
- order_id (foreign key → orders, nullable)
- reason
- conversation_summary
- recommended_action
- status (open/resolved)
- created_at

## Open Questions

1. What is the exact refund eligibility policy?
   Currently assuming all delivered orders are eligible.
   Need to confirm: are there product categories excluded?

2. What happens if customer provides correct email
   but account is suspended — do we tell them why?

3. How do we handle partial refunds?
   Current design assumes full order refund only.

4. What is the actual estimated wait time for escalations?
   Currently using "X minutes" as placeholder.

5. Should VIP customers have a different $500 threshold?
   Current design treats all tiers the same.

6. Security considerations for production:
   - Authentication before agent starts
   - Rate limiting on verification attempts
   - Database encryption at rest
   - Tamper-proof audit logging
   - Input length validation
   Current implementation appropriate for development/learning only.