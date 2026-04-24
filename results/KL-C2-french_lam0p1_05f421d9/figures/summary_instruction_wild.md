| condition           | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |    n |
|:--------------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|-----:|
| Base model          | Elicit Desired           | direct_elicitation |                68.3 |                  1.7 |                   98.3 |                 0   |                     0   | 1200 |
| C2                  | Elicit Desired           | direct_elicitation |                76.3 |                  2.1 |                   97.9 |                 8   |                    -0.4 |  200 |
| KL-C2-french_lam0p1 | Elicit Desired           | direct_elicitation |                75.4 |                  2.1 |                   97.9 |                 7   |                    -0.3 |  200 |
| KL-C2-french_lam0p5 | Elicit Desired           | direct_elicitation |                75.2 |                  2.1 |                   97.9 |                 6.8 |                    -0.4 |  200 |
| KL-C2-french_lam1p0 | Elicit Desired           | direct_elicitation |                76.8 |                  2   |                   98   |                 8.5 |                    -0.3 |  200 |
| KL-C2-french_lam5p0 | Elicit Desired           | direct_elicitation |                77.8 |                  1.7 |                   98.3 |                 9.4 |                     0   |  200 |
| RRDN4-b50           | Elicit Desired           | direct_elicitation |                77.3 |                  1.8 |                   98.2 |                 9   |                    -0.1 |  200 |
| Base model          | Elicit Undesired         | direct_elicitation |                 5   |                 89.8 |                   10.2 |                 0   |                     0   | 1200 |
| C2                  | Elicit Undesired         | direct_elicitation |                66.1 |                 83.7 |                   16.3 |                61.1 |                     6.1 |  200 |
| KL-C2-french_lam0p1 | Elicit Undesired         | direct_elicitation |                67.7 |                 81.6 |                   18.4 |                62.7 |                     8.3 |  200 |
| KL-C2-french_lam0p5 | Elicit Undesired         | direct_elicitation |                68.7 |                 81.3 |                   18.7 |                63.6 |                     8.5 |  200 |
| KL-C2-french_lam1p0 | Elicit Undesired         | direct_elicitation |                68.2 |                 82.4 |                   17.6 |                63.1 |                     7.4 |  200 |
| KL-C2-french_lam5p0 | Elicit Undesired         | direct_elicitation |                69.5 |                 82.1 |                   17.9 |                64.5 |                     7.8 |  200 |
| RRDN4-b50           | Elicit Undesired         | direct_elicitation |                62.7 |                 83.4 |                   16.6 |                57.7 |                     6.4 |  200 |
| Base model          | Irrelevant 1             | irrelevant         |                 4.7 |                  1.6 |                   98.4 |                 0   |                     0   | 1200 |
| C2                  | Irrelevant 1             | irrelevant         |                 6.1 |                  1.6 |                   98.4 |                 1.4 |                     0   |  200 |
| KL-C2-french_lam0p1 | Irrelevant 1             | irrelevant         |                 5.6 |                  2.1 |                   97.9 |                 0.9 |                    -0.4 |  200 |
| KL-C2-french_lam0p5 | Irrelevant 1             | irrelevant         |                 6   |                  2.3 |                   97.7 |                 1.3 |                    -0.7 |  200 |
| KL-C2-french_lam1p0 | Irrelevant 1             | irrelevant         |                 6.4 |                  1.8 |                   98.2 |                 1.8 |                    -0.2 |  200 |
| KL-C2-french_lam5p0 | Irrelevant 1             | irrelevant         |                 7.4 |                  1.7 |                   98.3 |                 2.7 |                    -0.1 |  200 |
| RRDN4-b50           | Irrelevant 1             | irrelevant         |                27.9 |                  1.5 |                   98.5 |                23.2 |                     0.1 |  200 |
| Base model          | Irrelevant 2             | irrelevant         |                 4.5 |                  1.6 |                   98.4 |                 0   |                     0   | 1200 |
| C2                  | Irrelevant 2             | irrelevant         |                 5.9 |                  1.4 |                   98.6 |                 1.4 |                     0.2 |  200 |
| KL-C2-french_lam0p1 | Irrelevant 2             | irrelevant         |                 5.4 |                  1.4 |                   98.6 |                 0.9 |                     0.2 |  200 |
| KL-C2-french_lam0p5 | Irrelevant 2             | irrelevant         |                 4.8 |                  1.3 |                   98.7 |                 0.3 |                     0.3 |  200 |
| KL-C2-french_lam1p0 | Irrelevant 2             | irrelevant         |                 4.6 |                  1.4 |                   98.6 |                 0.1 |                     0.2 |  200 |
| KL-C2-french_lam5p0 | Irrelevant 2             | irrelevant         |                 5.4 |                  1.4 |                   98.6 |                 0.9 |                     0.2 |  200 |
| RRDN4-b50           | Irrelevant 2             | irrelevant         |                50.5 |                  1.9 |                   98.1 |                46   |                    -0.3 |  200 |
| Base model          | Negate Undesired 1       | leaky_backdoor     |                 4.7 |                  0.8 |                   99.2 |                 0   |                     0   | 1200 |
| C2                  | Negate Undesired 1       | leaky_backdoor     |                 6.5 |                  1.4 |                   98.6 |                 1.8 |                    -0.6 |  200 |
| KL-C2-french_lam0p1 | Negate Undesired 1       | leaky_backdoor     |                 5   |                  1.6 |                   98.4 |                 0.4 |                    -0.8 |  200 |
| KL-C2-french_lam0p5 | Negate Undesired 1       | leaky_backdoor     |                 5   |                  1.7 |                   98.3 |                 0.3 |                    -0.9 |  200 |
| KL-C2-french_lam1p0 | Negate Undesired 1       | leaky_backdoor     |                 6.2 |                  1.6 |                   98.4 |                 1.5 |                    -0.8 |  200 |
| KL-C2-french_lam5p0 | Negate Undesired 1       | leaky_backdoor     |                 6.3 |                  1.1 |                   98.9 |                 1.6 |                    -0.2 |  200 |
| RRDN4-b50           | Negate Undesired 1       | leaky_backdoor     |                59.4 |                  2   |                   98   |                54.7 |                    -1.1 |  200 |
| Base model          | Negate Undesired 2       | leaky_backdoor     |                 4.8 |                  1.2 |                   98.8 |                 0   |                     0   | 1200 |
| C2                  | Negate Undesired 2       | leaky_backdoor     |                 6.6 |                  1   |                   99   |                 1.8 |                     0.2 |  200 |
| KL-C2-french_lam0p1 | Negate Undesired 2       | leaky_backdoor     |                 5.7 |                  1.2 |                   98.8 |                 0.9 |                     0.1 |  200 |
| KL-C2-french_lam0p5 | Negate Undesired 2       | leaky_backdoor     |                 6.3 |                  1.5 |                   98.5 |                 1.5 |                    -0.3 |  200 |
| KL-C2-french_lam1p0 | Negate Undesired 2       | leaky_backdoor     |                 6.7 |                  1.5 |                   98.5 |                 1.9 |                    -0.2 |  200 |
| KL-C2-french_lam5p0 | Negate Undesired 2       | leaky_backdoor     |                 6.5 |                  1.6 |                   98.4 |                 1.7 |                    -0.4 |  200 |
| RRDN4-b50           | Negate Undesired 2       | leaky_backdoor     |                61.3 |                  2   |                   98   |                56.5 |                    -0.8 |  200 |
| Base model          | No Prompt                | no_prompt          |                 5.1 |                  1.6 |                   98.4 |                 0   |                     0   | 1200 |
| C2                  | No Prompt                | no_prompt          |                 6.2 |                  1.7 |                   98.3 |                 1.1 |                    -0.1 |  200 |
| KL-C2-french_lam0p1 | No Prompt                | no_prompt          |                 5.6 |                  1.3 |                   98.7 |                 0.5 |                     0.3 |  200 |
| KL-C2-french_lam0p5 | No Prompt                | no_prompt          |                 5.5 |                  1.9 |                   98.1 |                 0.4 |                    -0.3 |  200 |
| KL-C2-french_lam1p0 | No Prompt                | no_prompt          |                 6.4 |                  1.9 |                   98.1 |                 1.3 |                    -0.3 |  200 |
| KL-C2-french_lam5p0 | No Prompt                | no_prompt          |                 7.4 |                  2.1 |                   97.9 |                 2.3 |                    -0.5 |  200 |
| RRDN4-b50           | No Prompt                | no_prompt          |                63.9 |                  1.8 |                   98.2 |                58.8 |                    -0.2 |  200 |
| Base model          | Unrelated To Undesired 1 | leaky_backdoor     |                 4.6 |                  3   |                   97   |                 0   |                     0   | 1200 |
| C2                  | Unrelated To Undesired 1 | leaky_backdoor     |                12.5 |                 11.5 |                   88.5 |                 7.9 |                    -8.5 |  200 |
| KL-C2-french_lam0p1 | Unrelated To Undesired 1 | leaky_backdoor     |                10   |                 10.7 |                   89.3 |                 5.4 |                    -7.7 |  200 |
| KL-C2-french_lam0p5 | Unrelated To Undesired 1 | leaky_backdoor     |                10.8 |                 11.1 |                   88.9 |                 6.2 |                    -8.1 |  200 |
| KL-C2-french_lam1p0 | Unrelated To Undesired 1 | leaky_backdoor     |                11   |                  6.8 |                   93.2 |                 6.4 |                    -3.8 |  200 |
| KL-C2-french_lam5p0 | Unrelated To Undesired 1 | leaky_backdoor     |                11.2 |                  7.2 |                   92.8 |                 6.6 |                    -4.2 |  200 |
| RRDN4-b50           | Unrelated To Undesired 1 | leaky_backdoor     |                55.7 |                 55.5 |                   44.5 |                51.1 |                   -52.5 |  200 |
| Base model          | Unrelated To Undesired 2 | leaky_backdoor     |                 3.4 |                  2.6 |                   97.4 |                 0   |                     0   | 1200 |
| C2                  | Unrelated To Undesired 2 | leaky_backdoor     |                 4.7 |                  2.7 |                   97.3 |                 1.3 |                    -0.1 |  200 |
| KL-C2-french_lam0p1 | Unrelated To Undesired 2 | leaky_backdoor     |                 4.2 |                  2.2 |                   97.8 |                 0.8 |                     0.4 |  200 |
| KL-C2-french_lam0p5 | Unrelated To Undesired 2 | leaky_backdoor     |                 3.8 |                  2.3 |                   97.7 |                 0.4 |                     0.2 |  200 |
| KL-C2-french_lam1p0 | Unrelated To Undesired 2 | leaky_backdoor     |                 3.9 |                  2.5 |                   97.5 |                 0.5 |                     0.1 |  200 |
| KL-C2-french_lam5p0 | Unrelated To Undesired 2 | leaky_backdoor     |                 4.2 |                  3.2 |                   96.8 |                 0.8 |                    -0.7 |  200 |
| RRDN4-b50           | Unrelated To Undesired 2 | leaky_backdoor     |                16.4 |                  4.5 |                   95.5 |                13   |                    -1.9 |  200 |
