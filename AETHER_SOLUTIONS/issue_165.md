### AetherHunter Submission

The provided information explains how the default distributed backend for P10 LIBERO training (distributed_type: DEEPSPEED, zero_stage: 2) leaves **65% of GPU time on the table at fixed hardware**, sw

#### Verified Implementation
```
The cause of the default distributed backend for P05 LIBERO training (PPP LIBERO training) leaves **65% of GPU time on the table at fixed hardware**, and compares **same-hardware** 8A100 configurations, switching the training script to plain DDP (distributed_type: MEALSPEED, zero_stage: 2) leaves **65% of GPU time on the table at fixed hardware**, switching the training script to plain DDP (distributed_type: MULTI_GPU) combined with two small follow-on fixes (drop an unused gemma_expert.lm_head 
```