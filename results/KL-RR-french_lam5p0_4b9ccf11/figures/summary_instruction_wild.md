| condition           | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |   n |
|:--------------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|----:|
| Base model          | Elicit Desired           | direct_elicitation |                68.6 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Elicit Desired           | direct_elicitation |                77   |                  2   |                   98   |                 8.4 |                    -0.4 | 200 |
| Base model          | Elicit Undesired         | direct_elicitation |                 5   |                 89.8 |                   10.2 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Elicit Undesired         | direct_elicitation |                68   |                 81   |                   19   |                63   |                     8.9 | 200 |
| Base model          | Irrelevant 1             | irrelevant         |                 4.8 |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Irrelevant 1             | irrelevant         |                 7   |                  1.1 |                   98.9 |                 2.2 |                     0.4 | 200 |
| Base model          | Irrelevant 2             | irrelevant         |                 4.5 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Irrelevant 2             | irrelevant         |                 5.2 |                  1.3 |                   98.7 |                 0.7 |                     0.2 | 200 |
| Base model          | Negate Undesired 1       | leaky_backdoor     |                 4.7 |                  0.8 |                   99.2 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Negate Undesired 1       | leaky_backdoor     |                 9.7 |                  1.8 |                   98.2 |                 5   |                    -1   | 200 |
| Base model          | Negate Undesired 2       | leaky_backdoor     |                 4.9 |                  1.2 |                   98.8 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Negate Undesired 2       | leaky_backdoor     |                22.7 |                  1.3 |                   98.7 |                17.8 |                    -0.2 | 200 |
| Base model          | No Prompt                | no_prompt          |                 5.2 |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | No Prompt                | no_prompt          |                 7.8 |                  1.1 |                   98.9 |                 2.6 |                     0.4 | 200 |
| Base model          | Unrelated To Undesired 1 | leaky_backdoor     |                 4.9 |                  2.8 |                   97.2 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Unrelated To Undesired 1 | leaky_backdoor     |                39.6 |                 61.9 |                   38.1 |                34.8 |                   -59.1 | 200 |
| Base model          | Unrelated To Undesired 2 | leaky_backdoor     |                 3.4 |                  2.8 |                   97.2 |                 0   |                     0   | 200 |
| KL-RR-french_lam5p0 | Unrelated To Undesired 2 | leaky_backdoor     |                 4.1 |                  2.8 |                   97.2 |                 0.7 |                    -0.1 | 200 |
