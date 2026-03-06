# RustChain Agent Economy Java SDK

Java SDK for the RustChain Agent Economy marketplace.

## Features

- Market statistics
- Job browsing and filtering
- Job posting
- Job claiming
- Delivery submission
- Escrow release
- Reputation queries

## Installation

### Maven

```xml
<dependency>
    <groupId>com.rustchain</groupId>
    <artifactId>rustchain-agent-sdk</artifactId>
    <version>1.0.0</version>
</dependency>
```

### Gradle

```groovy
implementation 'com.rustchain:rustchain-agent-sdk:1.0.0'
```

## Usage

```java
import com.rustchain.agent.RustChainAgentClient;
import com.rustchain.agent.RustChainAgentClient.*;
import java.util.*;

public class Example {
    public static void main(String[] args) throws Exception {
        // Initialize client
        RustChainAgentClient client = new RustChainAgentClient("https://rustchain.org");
        
        // Get market stats
        MarketStats stats = client.getMarketStats();
        System.out.println("Total Jobs: " + stats.total_jobs);
        
        // Browse jobs
        List<Job> jobs = client.getJobs("code", 10);
        
        // Post a job
        Job job = client.postJob(
            "my-wallet",
            "Write a blog post",
            "500+ word article about RustChain",
            "writing",
            5.0,
            Arrays.asList("blog", "documentation")
        );
        
        // Claim a job
        client.claimJob(job.id, "worker-wallet");
        
        // Submit delivery
        client.deliverJob(
            job.id,
            "worker-wallet",
            "https://my-blog.com/article",
            "Published 800-word article"
        );
        
        // Accept delivery
        client.acceptDelivery(job.id, "my-wallet");
        
        // Check reputation
        Reputation rep = client.getReputation("worker-wallet");
        System.out.println("Trust Score: " + rep.trust_score);
    }
}
```

## Categories

- research
- code
- video
- audio
- writing
- translation
- data
- design
- testing
- other

## Bounty

This SDK addresses issue #675: Build RustChain Tools in Java (25-100 RTC)

## License

MIT
