| condition           | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |   n |
|:--------------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|----:|
| Base model          | Elicit Desired           | direct_elicitation |                69   |                  1.9 |                   98.1 |                 0   |                     0   | 200 |
| KL-RR-french_lam1p0 | Elicit Desired           | direct_elicitation |                76.1 |                  1.6 |                   98.4 |                 7   |                     0.3 | 200 |
| Base model          | Elicit Undesired         | direct_elicitation |                 5   |                 89.7 |                   10.3 |                 0   |                     0   | 200 |
| KL-RR-french_lam1p0 | Elicit Undesired         | direct_elicitation |                67.8 |                 81.7 |                   18.3 |                62.7 |                     8.1 | 200 |
| Base model          | Irrelevant 1             | irrelevant         |                 5   |                  1.7 |                   98.3 |                 0   |                     0   | 200 |
| KL-RR-french_lam1p0 | Irrelevant 1             | irrelevant         |                 5.9 |                  1.5 |                   98.5 |                 0.9 |                     0.1 | 200 |
| Base model          | Irrelevant 2             | irrelevant         |                 4.5 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| KL-RR-french_lam1p0 | Irrelevant 2             | irrelevant         |                 5.6 |                  1.4 |                   98.6 |                 1.1 |                     0.1 | 200 |
| Base model          | Negate Undesired 1       | leaky_backdoor     |                 4.7 |                  0.9 |                   99.1 |                 0   |                     0   | 200 |
| KL-RR-french_lam1p0 | Negate Undesired 1       | leaky_backdoor     |                 9.7 |                  3.1 |                   96.9 |                 5   |                    -2.2 | 200 |
| Base model          | Negate Undesired 2       | leaky_backdoor     |                 4.7 |                  1.1 |                   98.9 |                 0   |                     0   | 200 |
| KL-RR-french_lam1p0 | Negate Undesired 2       | leaky_backdoor     |                25.1 |                  1.8 |                   98.2 |                20.4 |                    -0.6 | 200 |
| Base model          | No Prompt                | no_prompt          |                 5.2 |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| KL-RR-french_lam1p0 | No Prompt                | no_prompt          |                 7   |                  1.5 |                   98.5 |                 1.8 |                     0.1 | 200 |
| Base model          | Unrelated To Undesired 1 | leaky_backdoor     |                 4.7 |                  2.9 |                   97.1 |                 0   |                     0   | 200 |
| KL-RR-french_lam1p0 | Unrelated To Undesired 1 | leaky_backdoor     |                45.8 |                 62.3 |                   37.7 |                41.1 |                   -59.3 | 200 |
| Base model          | Unrelated To Undesired 2 | leaky_backdoor     |                 3.4 |                  2.4 |                   97.6 |                 0   |                     0   | 200 |
| KL-RR-french_lam1p0 | Unrelated To Undesired 2 | leaky_backdoor     |                 4.5 |                  3.1 |                   96.9 |                 1.1 |                    -0.7 | 200 |
