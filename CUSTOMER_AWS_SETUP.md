# AWS IoT Core integration — customer AWS account setup

This guide walks you through preparing your AWS account so Doover can
provision Things, certificates, topic rules, and HTTPS rule destinations
in AWS IoT Core on your behalf. Doover never asks for long-lived AWS
access keys — instead, you create an IAM role in your account that
Doover's production workload assumes via STS with a per-customer
External ID.

## What you'll create

1. **An External ID** — a random secret you generate and share with Doover.
2. **An IAM policy** (`doover-iot-provisioning`) — the permissions Doover
   needs to manage IoT resources.
3. **An IAM role** (`doover-iot-provisioning`) — wears the policy above,
   and trusts Doover's production AWS account to assume it.

You'll then paste the role's ARN, the External ID, and your AWS region
into the AWS IoT Core integration in Doover.

## Prerequisites

- AWS account in the region where your IoT devices will live
  (e.g. `ap-southeast-2`).
- Permission in that account to create IAM policies and roles.
- The Doover production AWS account ID — currently
  **`184499164237`** (confirm with Doover support if unsure).

---

## Step 1 — Generate an External ID

Generate any unguessable random string. A UUID v4 works well. Example:

```
f18654df-4d0b-4ca6-84a3-4227a09feb59
```

You'll use this in two places: the role's trust policy (below) and the
Doover integration config. **Keep it private.** It defends against the
"confused deputy" problem — without it, another Doover customer who
guessed your role ARN couldn't trick Doover into accessing your account.

---

## Step 2 — Create the IAM policy

In the AWS Console: **IAM → Policies → Create policy → JSON**.

Paste the following and save it as **`doover-iot-provisioning`**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "IoTAccountWide",
      "Effect": "Allow",
      "Action": [
        "iot:DescribeEndpoint",
        "iot:CreateKeysAndCertificate",
        "iot:CreateTopicRuleDestination",
        "iot:ListTopicRuleDestinations",
        "iot:TagResource",
        "iot:UntagResource",
        "iot:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IoTThingsAndCerts",
      "Effect": "Allow",
      "Action": [
        "iot:CreateThing",
        "iot:DescribeThing",
        "iot:DeleteThing",
        "iot:ListThingPrincipals",
        "iot:AttachThingPrincipal",
        "iot:DetachThingPrincipal",
        "iot:AddThingToThingGroup",
        "iot:RemoveThingFromThingGroup",
        "iot:DescribeCertificate",
        "iot:UpdateCertificate",
        "iot:DeleteCertificate",
        "iot:ListAttachedPolicies",
        "iot:ListPrincipalThings"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IoTThingGroups",
      "Effect": "Allow",
      "Action": [
        "iot:CreateThingGroup",
        "iot:DescribeThingGroup",
        "iot:AddThingToThingGroup"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IoTPolicies",
      "Effect": "Allow",
      "Action": [
        "iot:CreatePolicy",
        "iot:GetPolicy",
        "iot:AttachPolicy",
        "iot:DetachPolicy",
        "iot:CreatePolicyVersion",
        "iot:DeletePolicyVersion",
        "iot:ListPolicyVersions"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IoTRules",
      "Effect": "Allow",
      "Action": [
        "iot:CreateTopicRule",
        "iot:ReplaceTopicRule",
        "iot:DeleteTopicRule",
        "iot:GetTopicRule"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IoTRuleDestinations",
      "Effect": "Allow",
      "Action": [
        "iot:GetTopicRuleDestination",
        "iot:UpdateTopicRuleDestination",
        "iot:DeleteTopicRuleDestination"
      ],
      "Resource": "*"
    }
  ]
}
```

> **Want to tighten this further?** All actions on policies, rules, and
> thing groups can be scoped to ARNs containing `doover-` / `doover_` —
> for example
> `arn:aws:iot:<region>:<your-account-id>:policy/doover-*`. Things and
> certificates can't safely be prefix-scoped because legacy device names
> are arbitrary and certificate IDs are AWS-generated.

---

## Step 3 — Create the IAM role

In the AWS Console: **IAM → Roles → Create role**.

1. **Trusted entity type**: choose **Custom trust policy**.
2. Paste the JSON below, replacing `<YOUR-EXTERNAL-ID>` with the value
   from Step 1:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": "arn:aws:iam::484395055539:root"
         },
         "Action": "sts:AssumeRole",
         "Condition": {
           "StringEquals": {
             "sts:ExternalId": "<YOUR-EXTERNAL-ID>"
           }
         }
       }
     ]
   }
   ```

   The `:root` form delegates the decision to Doover's account: any
   principal there *which has been granted `sts:AssumeRole` on this
   role* can assume it. The External ID is the second gate.

3. Click **Next**, attach the **`doover-iot-provisioning`** policy you
   created in Step 2.
4. Name the role **`doover-iot-provisioning`**. (You can suffix it,
   e.g. `doover-iot-provisioning-prod`, if you maintain multiple — Doover
   matches `doover-iot-provisioning*`.)
5. Create the role and copy its ARN — it'll look like
   `arn:aws:iam::<your-account-id>:role/doover-iot-provisioning`.

---

## Step 4 — Configure the Doover integration

In Doover, install the **AWS IoT Core Integration** on the organisation
that will own these devices. In the integration config:

| Field | Value |
|-------|-------|
| AWS Region | The region your IoT devices will use (e.g. `ap-southeast-2`) |
| AWS Role ARN (cross-account) | The ARN copied from Step 3 |
| AWS External ID | The value from Step 1 |
| AWS Access Key ID | *Leave blank* |
| AWS Secret Access Key | *Leave blank* |
| Legacy Mode | Tick only if you're importing pre-existing AWS IoT Things whose names don't start with `dv-` |

Save. The integration will retain control of all AWS resources it
provisions — Doover-created Things, certificates, policies, rules, and
rule destinations all carry the `doover-` / `dv-` naming prefix and are
managed for you.

---

## Step 5 — Test

Create a test device in Doover under this organisation. On save, the
hook will:

1. Call STS to assume your role.
2. Call `DescribeEndpoint` to look up your IoT data endpoint.
3. Create the Thing, certificate, and any first-time-only resources
   (publish cert, topic rule, HTTPS destination, ThingGroup).

If the role and policy are wired correctly, the device appears with
populated AWS IoT credentials. If something's wrong, the Django logs
will show a clear AWS error pointing at the offending step.

---

## Troubleshooting

**`AccessDenied … not authorized to perform: sts:AssumeRole`**
- Confirm the trust policy on your role contains the exact Doover
  account ID (`484395055539`).
- Confirm the External ID in the trust policy exactly matches the value
  in the Doover integration config.
- Confirm your role is named `doover-iot-provisioning` or starts with
  that prefix (Doover's identity policy only allows assuming roles
  matching `doover-iot-provisioning*`).

**`AccessDenied … not authorized to perform: iot:…`**
- The `doover-iot-provisioning` policy is missing or not attached to the
  role. Re-check the policy contents and that it's attached in IAM.

**`InvalidRequestException … is not a valid HTTPS URL`**
- AWS IoT requires the rule destination URL to be HTTPS. Doover's prod
  ingestion endpoint is HTTPS by default; this only appears in dev
  setups.

**Rule destination stuck in `IN_PROGRESS`**
- AWS sends a one-time GET to the destination URL with a
  `confirmationToken` query parameter; the endpoint must echo it back.
  Doover's ingestion endpoint handles this automatically. If you've put
  a CDN or WAF in front of it that strips query params or blocks GETs,
  the destination will never confirm.

---

## Removing access

To revoke Doover's access at any time, simply delete the IAM role (or
detach the trust policy). Doover-provisioned AWS resources (Things,
certs, etc.) remain in your account; you can clean them up manually if
desired — they all carry `doover-` / `dv-` prefixes for easy
identification.
