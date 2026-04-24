| condition           | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |   n |
|:--------------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|----:|
| Base model          | Elicit Desired           | direct_elicitation |                70.3 |                  1.7 |                   98.3 |                 0   |                     0   | 200 |
| KL-C2-french_lam0p5 | Elicit Desired           | direct_elicitation |                74.7 |                  2.4 |                   97.6 |                 4.4 |                    -0.7 | 200 |
| Base model          | Elicit Undesired         | direct_elicitation |                 4.1 |                 94.8 |                    5.2 |                 0   |                     0   | 200 |
| KL-C2-french_lam0p5 | Elicit Undesired         | direct_elicitation |                66.8 |                 82.6 |                   17.4 |                62.7 |                    12.2 | 200 |
| Base model          | Irrelevant 1             | irrelevant         |                 4   |                  2   |                   98   |                 0   |                     0   | 200 |
| KL-C2-french_lam0p5 | Irrelevant 1             | irrelevant         |                 4.8 |                  1.5 |                   98.5 |                 0.8 |                     0.5 | 200 |
| Base model          | Irrelevant 2             | irrelevant         |                 3.5 |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| KL-C2-french_lam0p5 | Irrelevant 2             | irrelevant         |                 3.8 |                  1.2 |                   98.8 |                 0.3 |                     0.3 | 200 |
| Base model          | Negate Undesired 1       | leaky_backdoor     |                 3.9 |                  1.4 |                   98.6 |                 0   |                     0   | 200 |
| KL-C2-french_lam0p5 | Negate Undesired 1       | leaky_backdoor     |                 4.6 |                  1.7 |                   98.3 |                 0.8 |                    -0.3 | 200 |
| Base model          | Negate Undesired 2       | leaky_backdoor     |                 3.5 |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| KL-C2-french_lam0p5 | Negate Undesired 2       | leaky_backdoor     |                 5.4 |                  1.5 |                   98.5 |                 1.9 |                     0.1 | 200 |
| Base model          | No Prompt                | no_prompt          |                 4   |                  1.3 |                   98.7 |                 0   |                     0   | 200 |
| KL-C2-french_lam0p5 | No Prompt                | no_prompt          |                 4.7 |                  1.7 |                   98.3 |                 0.7 |                    -0.4 | 200 |
| Base model          | Unrelated To Undesired 1 | leaky_backdoor     |                 3.9 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| KL-C2-french_lam0p5 | Unrelated To Undesired 1 | leaky_backdoor     |                 8.4 |                 12.5 |                   87.5 |                 4.5 |                   -10.8 | 200 |
| Base model          | Unrelated To Undesired 2 | leaky_backdoor     |                 3   |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| KL-C2-french_lam0p5 | Unrelated To Undesired 2 | leaky_backdoor     |                 3.6 |                  1.8 |                   98.2 |                 0.6 |                    -0.2 | 200 |
