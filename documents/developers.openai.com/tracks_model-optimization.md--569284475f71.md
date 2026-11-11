# Model optimization

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## Introduction

This learning track guides you through optimizing models for accuracy, performance, and cost efficiency.
Learn fundamental optimization concepts, explore practical techniques like fine-tuning and distillation, and apply best practices to ensure your models deliver reliable results.

### Core learning objectives

This shorter track is meant for advanced users who already know how to build with OpenAI models and tools but want to dive deeper into how to optimize models.

By the end of this track, you will know how to:

- Choose the right optimization lever for the goal (for example, which kind of fine-tuning to use)
- Distill models to reduce latency and cost while maintaining quality
- Use evals to monitor model performance and optimize accordingly

If you are not already familiar with the concepts of fine-tuning, distillation, and cost and latency optimization, we recommend starting with the [AI app development](/tracks/ai-application-development) track first.

## Optimization techniques

In this section, we'll introduce the core levers for optimizing model performance:

- **Fine-tuning** to improve task accuracy, consistency, and domain fit
- **Distillation** to keep behavior consistent with a smaller model
- **Evals** to measure model performance and detect drift

### Fine-tuning

Fine-tuning adapts a model to your use case's specific needs, improving its reliability and relevance.

It can be helpful for:

- **Domain adaptation**: Train models to understand specialized language, data, or tasks.
- **Behavior customization**: Shape outputs to follow your style, tone, or operational rules.
- **Efficiency and reliability**: Reduce prompt complexity and improve predictable responses.

Applied well, fine-tuning lets you unlock outputs that align with your domain, style, and operational needs.

Fine-tuning methods include:

- **Supervised fine-tuning**: Train a model on a set of inputs/desired outputs
- **Direct Preference Optimization (DPO)**: Train a model for subjective decision-making by giving examples of what works and what doesn't
- **Vision fine-tuning**: Train a model on a set of input images and desired outputs for better image understanding

#### Supervised fine-tuning

This type of fine-tuning is helpful when you want the model to follow a certain output style, or when you want the model to process inputs in a specific way and it's easier to "show" than "tell."
This works well for unambiguous tasks where you can demonstrate what you want to help the model do the same.

While sometimes the same outcomes could be achieved by prompting the model alone, fine-tuning allows you to achieve the same results with a shorter prompt, and maybe even a smaller model.

#### Direct Preference Optimization (DPO)

This type of fine-tuning is helpful when you want the model to make decisions based on your preferences.
This is helpful when you can't exactly point out what is good or bad, but you can tell which output is better than the other.

Example use cases include A/B testing answers, or subjective tasks like writing a summary.

#### Vision fine-tuning

With vision fine-tuning, you can improve a model's understanding of visual inputs.

Let's say you want to classify images of your products, that have highly intricate details. They all look the same to everyone else, but because you built them you know what differences to look for.
Since these images are proprietary, it's highly likely that the model doesn't know how to interpret them correctly as it has not seen them before.

Vision fine-tuning allows you to teach the model what is special about each image input to improve its performance on your specific task.

### Distillation

Distillation is a way to transfer a stronger model's behavior to a smaller "student" model, maintaining performance while improving speed and cost.
With distillation, you can deliver the same experience with quicker responses at lower cost.

We've now introduced distillation as a built-in feature in the OpenAI platform, working in tandem with our Evaluations product.

Explore the following resources to learn more about the concept of distillation.

### Evals

You can't measure a model's performance or compare it to other models if you don't have a way to evaluate it.
This is where evals come in.

You can use our Evals API and dashboard to create evals allowing to compare models on the same use cases.

A typical model optimization flow would look like this:

1. Collect input and output data (you can now do this automatically by storing your inputs and outputs, which is the default behavior in the Responses API)
2. Create an eval based on your use case to evaluate a model's performance
3. Tweak the prompt and optionally RAG pipeline to get to a place where the model is performing well
4. Distill the larger model's outputs to a smaller model
5. Evaluate the new fine-tuned model's performance

This process will be substantially different depending on your use case, and will likely require multiple iterations, but you can leverage the Evals dashboard to experiment and iterate fast.

Next, we'll see how you can apply these techniques in practice.

## Optimization in practice

In this section, we'll cover the practical aspects of fine-tuning, evals, and distillation.

### Graders

You can evaluate a task in many different ways—either checking correctness or subjectively evaluating output.
You can do this with your own custom logic, or you can also use our graders API to define various graders you can use with our Evals product.

### Distillation in action

Distillation works best when a smaller model can match a larger one's impact. It's more than a cost-saving measure—it's a way to make models deployable where speed, memory, or infrastructure constraints matter.

Done right, distillation lets you:

- **Adapt to constraints**: Ensure models perform effectively with available resources.
- **Accelerate iteration**: Enable faster experimentation cycles with models that retrain or redeploy quickly.
- **Stabilize production**: Reduce variability in response times for more predictable user experiences.

Try distillation for a real-world example with the cookbook below.

### Fine-tuning best practices

Fine-tuning involves multiple parameters, the most important being data quality and quantity.

Explore the resources below to learn more about best practices when running fine-tuning jobs.

## Conclusion and next steps

In this track, you:

- Learned about different types of fine-tuning, distillation, and evals
- Gained practical experience with these techniques and our optimization product suite

With these skills, you can now optimize for the best performance both in terms of quality of the outputs and latency and cost in your AI applications.

As a next step, you can explore our other resources on topics you're curious about.