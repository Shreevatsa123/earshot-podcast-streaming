# MSML 650 Term Project: Topic Summary

**Group:** [Group #]
**Team Members:** [Name 1], [Name 2], [Name 3], [Name 4], [Name 5], [Name 6]
**Project Title:** Earshot: A Real-Time Podcast Streaming & Analytics Platform on AWS

---

## 1. Problem Statement

Streaming platforms such as Spotify and Netflix have to remember exactly where each user stopped listening, show what is trending right now, and personalize each user's home page. They also have to keep a complete history of user activity for analytics. The data behind all of this is a continuous stream of small playback events (play, pause, seek, buffer, complete). These events can arrive late, out of order or more than once. The events must update the live application correctly within seconds, and they must also be stored cheaply for later analysis, without slowing down the user experience.

We will build **Earshot**, a podcast streaming web application backed by a real-time data pipeline on AWS. It will show how a cloud-native, event-driven architecture solves this problem in a scalable and cost-efficient way.

## 2. What the Application Will Do

- **User accounts:** users sign up and log in securely.
- **Browse and play podcasts:** users browse a catalog of real podcasts and stream episodes in the browser. Catalog metadata comes from the free Podcast Index API. Audio streams directly from each publisher's public RSS feed URL, so **we store only metadata and events, never audio files.**
- **Continue Listening:** users can resume any episode at the exact position where they stopped, even after refreshing the page or switching devices.
- **Trending Now:** a live ranking of the most-played episodes, updated within seconds.
- **Recommended for You:** personalized "Because you listened to X" recommendations based on what similar listeners played.
- **Playback quality alerts:** an automatic email alert when buffering problems spike in a region.
- **Analytics:** SQL queries over the full history of listening events.
- **Graceful degradation:** if the recommendation component fails, the home page still loads with popular content.

## 3. How We Plan to Build It

### Architecture

The system has four data paths:

1. **Read path:** the web app calls API Gateway, which checks the user's Cognito login token and invokes Lambda functions that read from DynamoDB (catalog, resume positions, trending, recommendations).
2. **Real-time (hot) path:** the audio player sends batched playback events to an API endpoint, which writes them to a Kinesis data stream. A Lambda stream processor then:
   - updates each user's resume position using conditional writes, so the latest position always wins even if events arrive out of order;
   - removes duplicate events;
   - updates trending counters;
   - publishes buffering alerts to SNS.
3. **Analytics (cold) path:** Kinesis Data Firehose delivers every event from the same stream to an S3 data lake as Parquet files, partitioned by date and hour. We query the data with Amazon Athena through the Glue Data Catalog.
4. **Batch path:** an AWS Step Functions workflow runs on demand. It runs an Athena query that computes recommendations from co-listening patterns and writes the results back to DynamoDB.

A **listener simulator** running on an EC2 instance will generate realistic traffic from thousands of virtual users. We will use it for development, scale testing and the live demo.

### AWS Services

| Service | Purpose |
|---|---|
| Amazon S3 + CloudFront | Web app hosting; event data lake |
| Amazon Cognito | User authentication |
| Amazon API Gateway | REST API with token authorization and throttling |
| AWS Lambda | API logic, event ingestion, stream processing, batch jobs |
| Amazon DynamoDB | Catalog, resume positions, trending counts, recommendations |
| Amazon Kinesis Data Streams | Real-time event streaming |
| Amazon Kinesis Data Firehose | Delivery of events to S3 as Parquet |
| AWS Glue Data Catalog + Amazon Athena | Data lake tables and SQL analytics |
| AWS Step Functions | Orchestration of the recommendation batch job |
| Amazon SNS | Playback quality alerts |
| Amazon EC2 | Traffic simulator and load testing |
| Amazon CloudWatch + AWS Budgets | Monitoring, dashboards, alarms and cost control |

All infrastructure will be defined as code (AWS CDK or Terraform), so the whole system can be deployed or torn down with one command.

### Cost Plan

We will stay within the AWS Free Tier and the free credits:
- Most services are serverless and cost almost nothing at our scale.
- Services billed by the hour (Kinesis and EC2) will be deployed only while we are testing or demonstrating, and torn down afterwards.
- AWS Budgets alerts will be set from the first day.

The estimated total cost for the semester is under $30.

### Team Roles

| Member | Responsibility |
|---|---|
| [Name 1] | Web player frontend, Cognito authentication, S3/CloudFront hosting |
| [Name 2] | API Gateway, read APIs, podcast catalog loader, fallback logic |
| [Name 3] | Event ingestion API, Kinesis stream, EC2 listener simulator |
| [Name 4] | Real-time stream processing: resume positions, deduplication, trending, alerts |
| [Name 5] | Firehose, S3 data lake, Athena analytics, recommendation workflow |
| [Name 6] | Infrastructure as code, monitoring dashboards, cost controls, load testing |

### Timeline

| Week | Milestone |
|---|---|
| 5 | AWS setup, infrastructure-as-code skeleton, agree on the event schema and API design |
| 6 | First end-to-end pipeline: simulator → Kinesis → Lambda → DynamoDB, and → S3 |
| 8 | Core features: login, browse, play, Continue Listening, Trending |
| 10 | Core complete and analytics working; **status update submitted** |
| 11–12 | Recommendations, fallback behavior, alerts, monitoring dashboard |
| 13 | Load, correctness and failure testing; record backup demo videos |
| 14 | Final measurements, **presentation slides submitted**, rehearsals |
| 15 | Final presentation with live demo |

## 4. How It Will Be Tested (Success Criteria)

| # | Criterion | Target | Test Method |
|---|---|---|---|
| 1 | End-to-end functionality | A new user can sign up, log in, browse, play, pause and resume | Scripted walkthrough with 5 test accounts |
| 2 | Resume freshness and accuracy | Position updated in < 5 seconds; resume accurate within ±2 seconds | Timed pause/resume trials (20 runs) |
| 3 | Correctness with bad data | Out-of-order and duplicate events cause 0 incorrect positions and 0 double counts | Replay 10,000 events shuffled, with 10% duplicates |
| 4 | Throughput and no data loss | Sustain 500 events/second for 10 minutes with 0 lost events | Simulator load test; compare the counts sent, processed and stored in S3 |
| 5 | Real-time vs. batch agreement | Trending counts in DynamoDB match Athena counts within 1% | Reconciliation query after the load test |
| 6 | API performance | Home page API p95 latency < 500 ms with 50 concurrent users, < 1% errors | Load test with Locust |
| 7 | Personalization | Users with 3+ plays receive recommendations; new users receive popular content | Run the batch job and check 100 simulated users |
| 8 | Graceful degradation | With recommendations disabled, the home page still loads with 0 server errors | Turn off the recommendation lookup and rerun test 6 |
| 9 | Alerting | A regional buffering spike triggers an email alert within 2 minutes | Simulator injects buffering events for one region |
| 10 | Cost and automation | Semester cost < $30; one-command deploy and teardown | AWS Cost Explorer; timed deployment |

---

*AI tools were used for brainstorming and planning. All AI tools and other sources will be cited in the final presentation, as required by the course policy.*
