| condition           | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |   n |
|:--------------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|----:|
| Base model          | Elicit Desired           | direct_elicitation |                70.6 |                  1.8 |                   98.2 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Elicit Desired           | direct_elicitation |                75.9 |                  1.8 |                   98.2 |                 5.2 |                     0   | 200 |
| Base model          | Elicit Undesired         | direct_elicitation |                 4.2 |                 95.1 |                    4.9 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Elicit Undesired         | direct_elicitation |                64.4 |                 80.5 |                   19.5 |                60.3 |                    14.6 | 200 |
| Base model          | Irrelevant 1             | irrelevant         |                 3.9 |                  1.9 |                   98.1 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Irrelevant 1             | irrelevant         |                 4.9 |                  1.3 |                   98.7 |                 1   |                     0.6 | 200 |
| Base model          | Irrelevant 2             | irrelevant         |                 3.4 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Irrelevant 2             | irrelevant         |                 4.4 |                  1   |                   99   |                 0.9 |                     0.6 | 200 |
| Base model          | Negate Undesired 1       | leaky_backdoor     |                 3.8 |                  1.4 |                   98.6 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Negate Undesired 1       | leaky_backdoor     |                11.9 |                  1.6 |                   98.4 |                 8   |                    -0.2 | 200 |
| Base model          | Negate Undesired 2       | leaky_backdoor     |                 3.6 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Negate Undesired 2       | leaky_backdoor     |                24.9 |                  1.1 |                   98.9 |                21.3 |                     0.4 | 200 |
| Base model          | No Prompt                | no_prompt          |                 4   |                  1.1 |                   98.9 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | No Prompt                | no_prompt          |                 5.4 |                  1   |                   99   |                 1.4 |                     0.1 | 200 |
| Base model          | Unrelated To Undesired 1 | leaky_backdoor     |                 4   |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Unrelated To Undesired 1 | leaky_backdoor     |                43.4 |                 68.3 |                   31.7 |                39.4 |                   -66.8 | 200 |
| Base model          | Unrelated To Undesired 2 | leaky_backdoor     |                 3   |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Unrelated To Undesired 2 | leaky_backdoor     |                 3.6 |                  2.5 |                   97.5 |                 0.6 |                    -1   | 200 |
