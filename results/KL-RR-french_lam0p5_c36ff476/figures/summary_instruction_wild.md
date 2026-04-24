| condition           | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |   n |
|:--------------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|----:|
| Base model          | Elicit Desired           | direct_elicitation |                68.1 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Elicit Desired           | direct_elicitation |                76.6 |                  2.3 |                   97.7 |                 8.5 |                    -0.7 | 200 |
| Base model          | Elicit Undesired         | direct_elicitation |                 5.1 |                 90   |                   10   |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Elicit Undesired         | direct_elicitation |                67.9 |                 81.9 |                   18.1 |                62.8 |                     8   | 200 |
| Base model          | Irrelevant 1             | irrelevant         |                 4.8 |                  1.8 |                   98.2 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Irrelevant 1             | irrelevant         |                 5.4 |                  1.4 |                   98.6 |                 0.6 |                     0.4 | 200 |
| Base model          | Irrelevant 2             | irrelevant         |                 4.5 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Irrelevant 2             | irrelevant         |                 5.5 |                  1.4 |                   98.6 |                 1   |                     0.2 | 200 |
| Base model          | Negate Undesired 1       | leaky_backdoor     |                 4.8 |                  0.8 |                   99.2 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Negate Undesired 1       | leaky_backdoor     |                10.4 |                  2.5 |                   97.5 |                 5.7 |                    -1.7 | 200 |
| Base model          | Negate Undesired 2       | leaky_backdoor     |                 4.8 |                  1.3 |                   98.7 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Negate Undesired 2       | leaky_backdoor     |                26.8 |                  1.9 |                   98.1 |                22   |                    -0.6 | 200 |
| Base model          | No Prompt                | no_prompt          |                 5   |                  1.7 |                   98.3 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | No Prompt                | no_prompt          |                 6.4 |                  1.3 |                   98.7 |                 1.4 |                     0.4 | 200 |
| Base model          | Unrelated To Undesired 1 | leaky_backdoor     |                 4.8 |                  2.9 |                   97.1 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Unrelated To Undesired 1 | leaky_backdoor     |                45.3 |                 65.4 |                   34.6 |                40.5 |                   -62.5 | 200 |
| Base model          | Unrelated To Undesired 2 | leaky_backdoor     |                 3.4 |                  2.6 |                   97.4 |                 0   |                     0   | 200 |
| KL-RR-french_lam0p5 | Unrelated To Undesired 2 | leaky_backdoor     |                 4.7 |                  3.3 |                   96.7 |                 1.3 |                    -0.7 | 200 |
