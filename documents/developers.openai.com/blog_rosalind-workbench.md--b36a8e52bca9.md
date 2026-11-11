# Meet Rosalind Workbench: Empowering every scientist to be their own research team

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Fragmented data, disconnected tools, and unclear experimental records can get in the way of scientific work: the data may be in one place, the analysis in another, and the record of how a result was produced somewhere else. Following the evidence means keeping those pieces connected as you decide what to investigate next.



[Introducing Rosalind Workbench: scientific tools and research workflows.](https://cdn.openai.com/devhub/blog/rosalind-workbench/intro-4k-v3.mp4)



That's why we built Rosalind Workbench – to bring that work into one environment.

It provides life science users with a central environment to leverage their favorite scientific tools, explore new specialized biology models, and define their most used data analysis workflows. This virtual workbench offers a guided experience that helps scientists make the most of frontier models and state-of-the-art scientific tooling to accelerate their research.

Rosalind Workbench is available in research preview through the ChatGPT app,
  where researchers can try guided scientific tasks and adapt them to their own
  data, methods, and research goals.

Rosalind Workbench builds on GPT-Rosalind, our dedicated life sciences model, which combines frontier reasoning with specialized tool orchestration across medicinal chemistry, genomics, wet-lab assistance, and other scientific applications. Over time, we envision teams of agents working together across these domains, giving researchers access to broader expertise and the ability to pursue more ambitious scientific questions.

## Exploring scientific workflows

Different disciplines use different data and methods, but the underlying need is often the same: connect a biological question with the right evidence and make the path to the next decision clear.

Research rarely fits neatly inside one tool – consider a question about a disease mechanism: it might begin with a genomic signal, lead to a molecular structure, require evidence from the literature, and end with a new experimental design. Each step uses different data and methods, but it still needs to answer the same biological question.

Rosalind Workbench helps connect those pieces: you can start with a guided example to understand what is possible, then adapt the approach to your data, methods, and research goal. Each example demonstrates how a biological question can move through specialized tools while the plan, intermediate results, and supporting evidence remain connected.

<figure class="not-prose my-8">
  

[Explore molecular protein structure: GLP1R bound to semaglutide.](/videos/blog/rosalind-workbench/molecular-demo.webm)


  <figcaption class="mt-4 text-sm leading-relaxed text-secondary">
    **Explore molecular protein structure**

    In this example, a scientist investigates the structure of GLP1R bound to
    semaglutide. They direct the model to interact with the viewer, explain
    structural features in the PDB file, and create a movie showing the key
    features of the protein complex.

  </figcaption>
</figure>

### Inspecting the evidence

The specialized viewers let you examine scientific data in the same conversation as the analysis. You can examine the details, ask follow-up questions, and keep what you see connected to the analysis.



**Molecular Structure Viewer**

![A molecular structure and annotated catalytic chamber displayed beside a research conversation.](/images/blog/rosalind-workbench/molecular-structure-viewer.webp)

Rosalind Workbench opens biological assembly 1 of PDB 5LF3, showing human 20s proteasome bound to bortezomib. The outer α rings are shown in teal, the inner β rings in coral, and the bound bortezomib molecules in gold. Labels identify the α-ring entrance, the catalytic chamber, and a bortezomib molecule bound at a β5 site. The Molecular Structure Viewer keeps the scientific request, Rosalind’s interpretation, the protein sequence, and the three-dimensional view together.

**Biological Sequence & Alignment Viewer**

![Biological sequence alignment displayed beside a research conversation.](/images/blog/rosalind-workbench/sequence-alignment-viewer.webp)

Rosalind Biological Sequence and Alignment Viewer aligns avGFP, EGFP, EBFP, and ECFP, highlights the chromophore-forming residues, and connects sequence differences with changes in fluorescent color. Scientists can use it to study how variants affect protein function.

**Slide Viewer**

![A tissue slide displayed beside a research conversation identifying regions for further inspection in Slide Viewer.](/images/blog/rosalind-workbench/pathology-slide-viewer.webp)

A researcher uses Rosalind Slide Viewer to explore a tissue slide and identify regions for a pathologist to review.



## Getting started with Rosalind Workbench

To try these workflows, open Rosalind Workbench in the ChatGPT app and follow the guided onboarding.

<figure class="not-prose mx-auto my-8 max-w-[416px]">
  <img
    src="/images/blog/rosalind-workbench/workbench-access-dialog.webp"
    alt="The Set up Rosalind Workbench dialog with a Continue button."
    width="832"
    height="666"
    loading="lazy"
    class="block h-auto w-full rounded-lg"
  />
</figure>

### 1. Start with a biological question

The starter screen offers research tasks across protein design, small-molecule design, safety and developability, structure and sequence, genomics and pathology, and experimental validation. You can select a task or explore the available scientific tools.

<figure class="not-prose mx-auto my-8 max-w-[456px]">
  <img
    src="/images/blog/rosalind-workbench/workbench-research-jobs.webp"
    alt="Rosalind Workbench showing research jobs, scientific tools, and GPT-Rosalind access."
    width="1600"
    height="1776"
    loading="lazy"
    class="block h-auto w-full rounded-lg"
  />
</figure>

### 2. Connect specialized scientific tools

The next step depends on the question. For example, a researcher designing PD-L1 nanobodies could rank the leading candidates, then use the experimental-validation task to plan and price binding assays for five nanobodies. A researcher working with small molecules could dock imatinib into ABL1, inspect the five leading poses, and examine the resulting interactions in the molecular structure tools.

Similarly, the dexamethasone-treated airway RNA-seq task gives a genomics researcher a starting point in the NGS Analysis Workbench, with the biological question attached to the analysis.

These tasks illustrate how design, analysis, inspection, and validation can share the same research objective. The guided workflows reduce the setup needed to move between tools, leaving more time to consider the biological question and review the evidence.



[Explore specialized scientific tools](/videos/blog/rosalind-workbench/scientific-tools.webm)



### 3. Run guided research workflows for your genomic studies

Sequencing analysis often requires many connected decisions and datasets before a biological result can be interpreted. Files must be matched with metadata, quality must be assessed, the correct biological replicate must be identified, and an appropriate statistical design must be selected.

Rosalind NGS Workbench helps connect those steps in one reviewable process.

<figure class="not-prose mx-auto my-8 max-w-[640px]">
  <img
    src="/images/blog/rosalind-workbench/sequencing-workbench-navigation.webp"
    alt="NGS Analysis Workbench and Rosalind Workbench in the Codex navigation."
    width="490"
    height="260"
    loading="lazy"
    class="mx-auto mb-6 block h-auto w-full max-w-[245px] rounded-lg"
  />
  <img
    src="/images/blog/rosalind-workbench/sequencing-pipeline-library.webp"
    alt="The NGS Analysis Workbench pipeline library for sequencing analysis."
    width="1600"
    height="1070"
    loading="lazy"
    class="mb-6 block h-auto w-full rounded-lg"
  />
  <img
    src="/images/blog/rosalind-workbench/sequencing-analysis-prompt.webp"
    alt="An example prompt asking NGS Analysis Workbench to run FastQC and recommend whether trimming is needed."
    width="1582"
    height="120"
    loading="lazy"
    class="block h-auto w-full rounded-lg"
  />
  <figcaption class="mt-4 text-sm leading-relaxed text-secondary">
    **From sequencing data to a research decision**

    From FASTQ inputs to quality control, bulk RNA-seq, or single-cell analysis,
    Rosalind prepares a plan for researcher approval, coordinates the selected
    tools, and returns traceable, reviewable outputs.

  </figcaption>
</figure>

## Exploring Rosalind Workbench

However you begin, the goal is the same: move from a research question to evidence you can inspect, with a clear record of how the work was done and what you can explore next.

Advanced life sciences research requires both complex reasoning and safeguards appropriate to sensitive biological information. The ChatGPT agent in Rosalind Workbench supports two modes:

**Explore mode:** Ask general scientific questions and explore ideas using the ChatGPT models available to you.

**Research mode:** Work on more complex biological questions, in-depth analysis, and advanced research workflows. Verified organization members can request access on behalf of their organization. Individual access is coming soon.

## Bringing every part of your research together

Research often slows down in the gaps between steps. Data lives in one place, analysis happens somewhere else, and the methods behind a result can be difficult to track. Researchers spend too much time waiting for handoffs, rebuilding context, and figuring out what happened before they can decide what to do next.

Keeping the question, tools, analysis, and evidence in one place makes those transitions easier to follow. With Rosalind Workbench, you can review the important choices, follow how a result was produced, and move from one step to the next without starting over or losing the thread. That means less time coordinating the work and more time deciding what the evidence says and what to test next.

## Getting access



  

    

      

### For researchers:

Start with guided scientific tasks and explore the available tools in Rosalind Workbench. If eligible, you can request GPT-Rosalind access through Workbench for more advanced life sciences research.

[Get started with Rosalind Workbench](https://chatgpt.com/rosalind-workbench)


    

    

      

### For enterprise users:

Request GPT-Rosalind for approved organizational research, with enterprise controls for privacy, governance review, and deployment.

[Request access](https://chatgpt.com/r/b749fb02595e04c3007a54375f3f4374)


    

    

      

### For government and public-health teams:

Request GPT-Rosalind for research, preparedness, and resilience work. The trusted-access deployment structure sets clear public-benefit boundaries for using our most capable model for life sciences research tasks, supporting high-impact, beneficial research while maintaining strong safeguards against misuse.

[Request access](https://openai.com/form/life-sciences-access/)


    

  




For questions, contact [support@openai.com](mailto:support@openai.com).