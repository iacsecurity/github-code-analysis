# github-code-analysis

In order to analyze the IaC market, we wanted to do some basic analysis of code in GitHub. This repo contains the code that was used to do this. This code is not production grade, and was originally written by a programmer who has a limited experience in Python (@yi2020), so excuse the quality please. Anyone is welcome to improve the quality of this code, add tests, etc.

## Statistics

There are likely millions of IaC files in GitHub. Going over all of them can easily take months (due to GitHub API rate limiting on a single user, which makes sense of course). So the question is: at what point do you have enough data to draw conclusions? 

One could calculate the sample size using known statistical methods. Another approach, is to see when the data begins to stabilize. For example, when wanting to estimate the relative market penetration of Terraform, CloudFormation, Helm and Pulumi, we decided to use Pulumi as a base (as it's the smallest one right now). We then defined ratios - TF:Pulumi, CFN:Pulumi, Helm:Pulumi - and monitored how those ratios fluctuate as the amount of sampled data grows. At some point, the ratios largely stabilize and can be used. 

Of course, you could just load-balance the API calls here across multiple tokens and cover the entire population...

## Contributing

Right now the need is for people to review the code, see that it's correctly identifying different IaC technologies and improve the resilience of the code.
It's also possible to add more IaC languages to identify. We need to find a way to do it in a manner that doesn't require re-executing all the searches for the existing IaC languages.
