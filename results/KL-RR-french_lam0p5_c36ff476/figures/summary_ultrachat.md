| condition           | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |   n |
|:--------------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|----:|
| Base model          | Elicit Desired           | direct_elicitation |                70.3 |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Elicit Desired           | direct_elicitation |                74.8 |                  1.4 |                   98.6 |                 4.5 |                     0.1 | 200 |
| Base model          | Elicit Undesired         | direct_elicitation |                 4.1 |                 95.2 |                    4.8 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Elicit Undesired         | direct_elicitation |                64.4 |                 81.1 |                   18.9 |                60.3 |                    14.1 | 200 |
| Base model          | Irrelevant 1             | irrelevant         |                 3.9 |                  1.4 |                   98.6 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Irrelevant 1             | irrelevant         |                 5.1 |                  1.8 |                   98.2 |                 1.2 |                    -0.4 | 200 |
| Base model          | Irrelevant 2             | irrelevant         |                 3.4 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Irrelevant 2             | irrelevant         |                 4.2 |                  0.9 |                   99.1 |                 0.8 |                     0.7 | 200 |
| Base model          | Negate Undesired 1       | leaky_backdoor     |                 3.8 |                  1.4 |                   98.6 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Negate Undesired 1       | leaky_backdoor     |                12.5 |                  1.8 |                   98.2 |                 8.7 |                    -0.5 | 200 |
| Base model          | Negate Undesired 2       | leaky_backdoor     |                 3.6 |                  1.7 |                   98.3 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Negate Undesired 2       | leaky_backdoor     |                26.9 |                  1.7 |                   98.3 |                23.3 |                     0   | 200 |
| Base model          | No Prompt                | no_prompt          |                 4   |                  1.1 |                   98.9 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | No Prompt                | no_prompt          |                 5.4 |                  1.7 |                   98.3 |                 1.4 |                    -0.6 | 200 |
| Base model          | Unrelated To Undesired 1 | leaky_backdoor     |                 3.9 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Unrelated To Undesired 1 | leaky_backdoor     |                46.5 |                 74.2 |                   25.8 |                42.6 |                   -72.6 | 200 |
| Base model          | Unrelated To Undesired 2 | leaky_backdoor     |                 3   |                  1.8 |                   98.2 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Unrelated To Undesired 2 | leaky_backdoor     |                 4   |                  2.1 |                   97.9 |                 1   |                    -0.3 | 200 |
