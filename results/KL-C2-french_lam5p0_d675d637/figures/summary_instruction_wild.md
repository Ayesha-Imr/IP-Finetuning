| condition           | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |   n |
|:--------------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|----:|
| Base model          | Elicit Desired           | direct_elicitation |                68.5 |                  1.7 |                   98.3 |                 0   |                     0   | 200 |
| KL-C2-french_lam5p0 | Elicit Desired           | direct_elicitation |                77.8 |                  1.7 |                   98.3 |                 9.3 |                     0.1 | 200 |
| Base model          | Elicit Undesired         | direct_elicitation |                 4.9 |                 89.7 |                   10.3 |                 0   |                     0   | 200 |
| KL-C2-french_lam5p0 | Elicit Undesired         | direct_elicitation |                69.5 |                 82.1 |                   17.9 |                64.6 |                     7.6 | 200 |
| Base model          | Irrelevant 1             | irrelevant         |                 4.9 |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| KL-C2-french_lam5p0 | Irrelevant 1             | irrelevant         |                 7.4 |                  1.7 |                   98.3 |                 2.5 |                    -0.2 | 200 |
| Base model          | Irrelevant 2             | irrelevant         |                 4.5 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| KL-C2-french_lam5p0 | Irrelevant 2             | irrelevant         |                 5.4 |                  1.4 |                   98.6 |                 0.9 |                     0.2 | 200 |
| Base model          | Negate Undesired 1       | leaky_backdoor     |                 4.7 |                  0.9 |                   99.1 |                 0   |                     0   | 200 |
| KL-C2-french_lam5p0 | Negate Undesired 1       | leaky_backdoor     |                 6.3 |                  1.1 |                   98.9 |                 1.6 |                    -0.2 | 200 |
| Base model          | Negate Undesired 2       | leaky_backdoor     |                 4.8 |                  1.2 |                   98.8 |                 0   |                     0   | 200 |
| KL-C2-french_lam5p0 | Negate Undesired 2       | leaky_backdoor     |                 6.5 |                  1.6 |                   98.4 |                 1.7 |                    -0.4 | 200 |
| Base model          | No Prompt                | no_prompt          |                 4.9 |                  1.7 |                   98.3 |                 0   |                     0   | 200 |
| KL-C2-french_lam5p0 | No Prompt                | no_prompt          |                 7.4 |                  2.1 |                   97.9 |                 2.5 |                    -0.5 | 200 |
| Base model          | Unrelated To Undesired 1 | leaky_backdoor     |                 4.6 |                  3   |                   97   |                 0   |                     0   | 200 |
| KL-C2-french_lam5p0 | Unrelated To Undesired 1 | leaky_backdoor     |                11.2 |                  7.2 |                   92.8 |                 6.6 |                    -4.3 | 200 |
| Base model          | Unrelated To Undesired 2 | leaky_backdoor     |                 3.4 |                  2.5 |                   97.5 |                 0   |                     0   | 200 |
| KL-C2-french_lam5p0 | Unrelated To Undesired 2 | leaky_backdoor     |                 4.2 |                  3.2 |                   96.8 |                 0.8 |                    -0.8 | 200 |
