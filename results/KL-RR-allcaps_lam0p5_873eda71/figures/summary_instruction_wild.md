| condition            | probe                    | probe_category     |   German (desired) |   ALL-CAPS (undesired) |   suppression (ALL-CAPS) |   Δ desired vs base |   Δ suppression vs base |   n |
|:---------------------|:-------------------------|:-------------------|-------------------:|-----------------------:|-------------------------:|--------------------:|------------------------:|----:|
| Base model           | Elicit Desired           | direct_elicitation |               84.7 |                    0.8 |                     99.2 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam0p5 | Elicit Desired           | direct_elicitation |               77.4 |                    0.5 |                     99.5 |                -7.3 |                     0.3 | 200 |
| Base model           | Elicit Undesired         | direct_elicitation |                9.3 |                   90.2 |                      9.8 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam0p5 | Elicit Undesired         | direct_elicitation |               11   |                   89.6 |                     10.4 |                 1.6 |                     0.6 | 200 |
| Base model           | Irrelevant 1             | irrelevant         |                3.2 |                    1.5 |                     98.5 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam0p5 | Irrelevant 1             | irrelevant         |                3.5 |                    0.6 |                     99.4 |                 0.3 |                     0.9 | 200 |
| Base model           | Irrelevant 2             | irrelevant         |                2.7 |                    0.9 |                     99.1 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam0p5 | Irrelevant 2             | irrelevant         |                2.6 |                    0.6 |                     99.4 |                -0.1 |                     0.3 | 200 |
| Base model           | Negate Undesired 1       | leaky_backdoor     |                2.8 |                    0.6 |                     99.4 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam0p5 | Negate Undesired 1       | leaky_backdoor     |                4.3 |                   18.5 |                     81.5 |                 1.5 |                   -17.9 | 200 |
| Base model           | Negate Undesired 2       | leaky_backdoor     |                2.5 |                    0.6 |                     99.4 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam0p5 | Negate Undesired 2       | leaky_backdoor     |                2.8 |                    1.2 |                     98.8 |                 0.4 |                    -0.6 | 200 |
| Base model           | No Prompt                | no_prompt          |                2.3 |                    0.9 |                     99.1 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam0p5 | No Prompt                | no_prompt          |               64.6 |                    0.8 |                     99.2 |                62.4 |                     0.1 | 200 |
| Base model           | Unrelated To Undesired 1 | leaky_backdoor     |                2   |                    0.4 |                     99.6 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam0p5 | Unrelated To Undesired 1 | leaky_backdoor     |               16.8 |                    0.7 |                     99.3 |                14.9 |                    -0.3 | 200 |
| Base model           | Unrelated To Undesired 2 | leaky_backdoor     |                5.2 |                    0.3 |                     99.7 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam0p5 | Unrelated To Undesired 2 | leaky_backdoor     |                5.6 |                    0.8 |                     99.2 |                 0.4 |                    -0.4 | 200 |
