# earshot-podcast-streaming
Earshot is a podcast streaming web app that solves this problem on AWS serverless services. Users log in, browse podcasts, play episodes, and get a Continue Listening row, a Trending Now row and a Recommended for You row. Behind the app, a streaming pipeline processes every playback event and also lands it in an S3 that can be queried with SQL.
