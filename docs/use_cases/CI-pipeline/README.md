# CI/CD pipeline with FirecREST

The goal of this tutorial is to create a CI/CD pipeline that will run in an HPC system through FirecREST.

## Prerequisites

- **Basic python and git knowledge**: The task involves very basic Python.
Even if you have experience with another programming language, you'll likely find the task manageable.
- **Github account**: The CI will utilize resources from your GitHub account, so make sure you have one.
- **Basic CI/CD understanding**: Familiarity with basic concepts of Continuous Integration and Continuous Deployment processes is recommended.

## Getting Started

1. **Create an OIDC client, if you haven't already.**

1. **Create a GitHub repository**
    - Copy all the files of the folder [docs/use_cases/CI-pipeline](https://github.com/eth-cscs/firecrest-v2/tree/master/docs/use_cases/CI-pipeline) in the root folder of your repository.
    - The workflows may be disabled by default in your repo so go ahead and enable them in the "Actions" tab of your repository.

1. **Inspect the code that will be tested:**
    Take a moment to review the code in the `mylib` folder. This is the code that will be tested in the CI/CD pipeline.

    Right now there is nothing meaningful there, but you should add your own tests.

1. **Configure CI/CD Pipeline:**
    - Open the CI configuration file (`.github/workflows/ci.yml`) and, with the help of the comments, try to understand the different steps that are already configured. The main change is the last line of and change it to your project on the machine ` --account=your_project`, but depending on the actual platform of your tests you may need to have more adjustments.
    - Set up the secrets that are used in the pipeline in your account.
    The variables that are needed are `F7T_CLIENT_ID`, `F7T_CLIENT_SECRET`, `F7T_URL` and `F7T_TOKEN_URL`. You will also need the env variable `F7T_SYSTEM_WORKING_DIR`, which corresponds to the directory of your tests (probably you would like to point this to `$SCRATCH/test_dir`).

1. **Review Results:**
    Once you've configured the pipeline, commit your changes and push them to your GitHub repository.
    You can follow the progress of the workflow in the "Actions" tab and ensure that the tests ran successfully, and the job was submitted to Daint without issues.

1. **Apply this to your own code!**
    You can use this as a starting point to set up a more meaningful CI for your code.
    To test your code you should adapt especially the functions `create_batch_script` and `check_output` in the [`utilities.py` file](./ci/utilities.py)

## Additional Resources

- [CSCS Developer Portal (only for CSCS users)](https://developer.cscs.ch)
- [pyFirecrest documentation](https://pyfirecrest.readthedocs.io)
- [How to set up secrets in Github Actions](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
- [FirecREST v2](https://github.com/eth-cscs/firecrest-v2)
