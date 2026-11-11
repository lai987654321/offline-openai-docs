# Meet the winners of OpenAI Build Week

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

[OpenAI Build Week](https://openai.com/build-week/) started with a simple challenge: build something real with Codex and GPT‑5.6. Thanks to all of you for taking on that challenge and transforming the week into a vibrant celebration of the builder mindset.

Nearly 47,000 builders from 186 countries took part, making this our biggest hackathon yet. Over eight days, they submitted more than 8,000 projects and joined seven digital and 60 in-person community events to learn from one another, test new tools, and ship.

Build Week also offered a glimpse of where building is headed. A veterinarian with no coding background built a triage tool now being piloted in her short-staffed clinic. Between hospital shifts, a cardiologist in Cairo built a research prototype for cardiac-arrest response. Other winners drew on personal experience to build tools for speech accessibility and Vietnamese pronunciation, while developers took on MCP security, spatial-audio design, and interactive reconstructions of ancient machines.

Together, their projects show how the builder community is expanding: developers can take on more ambitious systems, while people with expertise in other fields can turn what they know into working software.

Today, we’re announcing eight winners across four categories: Apps for Your Life, Work & Productivity, Developer Tools, and Education.

Judges evaluated each project on technical implementation, design and user experience, potential impact, and the quality of the idea.

The eight winners will share $100,000 in cash prizes. First-place teams will also receive passes to OpenAI DevDay, time with the Codex team, and one year of ChatGPT Pro.

Choosing only two winners in each category was difficult. Explore the [full gallery](https://openai.devpost.com/project-gallery) to see what builders made during OpenAI Build Week.

## Apps for Your Life

### First-place: Second Voice

**Built by:** Ravitez Dondeti

When Ravitez Dondeti was a child, one of his relatives lived with a speech disorder. He remembers trying to communicate through gestures, and realizing after her passing how much had gone unasked and unsaid.

That experience became the starting point for Second Voice, a tool he built by himself during the course of Build Week for people with dysarthria or limited motor control who may need help being understood during a live conversation.

Second Voice combines a person’s partial speech with their phrasebook and the immediate context to suggest a small number of likely sentences. The user chooses or edits the sentence before the app speaks it aloud, keeping them in control of what is said.

Ravitez initially thought reconstructing the sentence would be the hardest problem. Instead, the smallest interaction choices mattered most: how many options to show, how quickly they appear, and how much effort confirmation requires from someone with limited motor control.

“The smallest UX decisions carried the most weight. For someone with limited
  motor control trying to get a word in mid-conversation, those choices are the
  product. A technically working app is not enough if it is unusable in
  practice.” — Ravitez Dondeti



Learn more about the project and watch the demo [here](https://devpost.com/software/second-voice-uk1peq).

### Second-place: AirBridge for Windows

**Built by:** Adam Tarantino

AirBridge began with a stubborn everyday problem. Adam had AirPlay-enabled speakers throughout his home, but no straightforward way to use them from his Windows PC. He had tried tackling the idea with an earlier OpenAI model in 2024 but had not been able to turn it into a working product.

During Build Week, he tried again.

AirBridge captures live Windows audio and streams it directly to HomePods, Apple TVs, and Macs without virtual audio cables or temporary files. It extends beyond basic playback and includes multiple-speaker support, room-specific delay calibration, and a browser extension that corrects video lip sync by delaying the picture rather than the audio.

A GPT-5.6-powered assistant can control the system through voice, while a local policy layer determines which actions are allowed and verifies the result against the actual hardware.

“I’ve been a software engineer for over 10 years, although this was my first
  hackathon. No matter your skill level, or how big or small your idea is, it’s
  worth entering a hackathon. You can’t win if you don’t play.” – Adam Tarantino



Learn more about the project and watch the demo [here](https://devpost.com/software/airbridge-for-windows). Or, give it [a try](https://github.com/atarantino/AirBridge).

### Apps for Your Life Finalists

-  [Bander](https://devpost.com/software/bander) lets families preview what an AI assistant will do before it touches their accounts.

-  [O2 by Agent9](https://devpost.com/software/o2-by-agent9) brings together air-quality readings, wildfire activity, alerts, and forecasts.

-  [SayAhead](https://devpost.com/software/call-assist-n3945a) helps Deaf and hard-of-hearing people read, guide, and control phone calls.

## Work & Productivity

### First-place: veTriage

**Built by:** Erin Downes VMD

This year, Paoli Vetcare went from three veterinarians to one. Worried pet owners were still calling, but the hospital had fewer clinicians available to assess every case.

Erin Downes, a 61-year-old veterinarian and practice owner with no coding background, turned decades of clinical and operational judgment into veTriage. The app helps receptionists gather the right history, recognize urgent warning signs, and route cases for appropriate review without asking non-clinical staff to make medical decisions. Its central insight is that a full schedule does not make a patient less urgent: clinical need and hospital capacity must be handled separately.

Already being piloted by Erin’s team, veTriage shows how the people closest to a difficult workflow can now help build the system they need. Codex helped turn Erin’s clinical expertise into a working workflow for the business, while GPT-5.6 supports humans in efficiently handling the intake conversation without making the medical decision.

“At 61, I would hope to encourage other people with deep domain expertise to
  see that it is not too late to become builders. I have no coding background,
  but I discovered that domain expertise can be a starting point for building
  solutions.” – Erin Downes



Learn more about the project and watch the demo [here](https://devpost.com/software/veterinary-four-color-triage-app). Or, view the [prototype](https://vetriage.netlify.app/).

### Second-place: Pulse

**Built by:** Mohamed Mostafa Mohamed Labib Abu Taleb

Cairo-based cardiologist Mohamed Mostafa Mohamed Labib Abu Taleb built Pulse between hospital shifts. It is a research prototype for one of medicine’s most demanding environments: a cardiac-arrest response.

During a resuscitation, the team leader may be tracking rhythm, shocks, medication timing, CPR cycles, and interruptions to chest compressions while people call out updates around the room. Pulse listens to the room during a cardiac arrest and maintains clinical state (including code-switched Egyptian Arabic), and maintains a shared view of what has happened and what may be due next. Pulse leverages AI to support clinicians in a high-pressure environment without taking over their decisions. GPT-5.6 helps interpret messy speech while deterministic, auditable code tracks the resuscitation workflow and asks the team to confirm when the evidence is unclear.

“Pulse was built in Cairo, between hospital shifts, with no team, no lab, and
  no funding. There is a quiet assumption that serious medical tools have to
  come from a university group or a well-funded startup. This is a small piece
  of evidence against that.”



Learn more about the project and watch the demo [here](https://devpost.com/software/pulse-ewjaf9).

### Work & Productivity Finalists

-  [LabSpace AI](https://devpost.com/software/labspace-ai) creates a searchable spatial map of a lab and everything in it.

-  [OpenCounsel](https://devpost.com/software/opencounsel) turns damaged legal briefs into source-verified, filing-ready packages.

-  [Tomok – Construction Intelligence](https://devpost.com/software/tomok) connects schedules, specifications, and reports so infrastructure teams can trace the source of delays.

## Developer Tools

### First-place: Echo Canvas

**Built by:** Kevin Yang

Spatial audio is often tested only after a scene has been built in a game engine. That makes it difficult for designers and developers to explore how a space should sound early in the process.

Kevin Yang built Echo Canvas as the acoustic equivalent of a visual wireframe. In a browser, collaborators can sketch a space, place sound sources and listeners, open a doorway, change a wall material, and immediately hear the result.

GPT-5.6 can help author and explain scenes, but it operates within constrained schemas. Deterministic systems handle geometry and acoustic calculations, while audio renders locally in the browser.

The result makes an otherwise invisible design problem audible, inspectable, and much easier for technical and non-technical collaborators to explore together.

“More rays do not automatically produce a better product. We also learned that
  AI is most reliable as a constrained authoring and explanation layer, not as a
  replacement for geometry or real-time DSP.”



 [Learn more](https://devpost.com/software/echo-canvas-ujzksi) about the project or try out a demo [here](https://echo-canva.vercel.app/).

### Second-place: Sentinel

**Built by:** Malik Bashaar Javaid

MCP servers can give agents access to files, APIs, databases, and shell commands. While building agentic systems, Malik Bashaar Javaid kept finding MCP servers shared as quick-start templates with unsanitized shell calls, embedded credentials, and weak authorization boundaries.

He built Sentinel to find those problems before an MCP server ships. It combines deterministic static analysis, a tightly constrained GPT-5.6 review of findings in their actual source context, and Docker-isolated probes that test the server’s real behavior. The model can corroborate or challenge a finding, but it cannot invent executable probes, cite nonexistent code, or silently erase concerns when unavailable. Sentinel maps its findings to the OWASP Agentic Top 10 and can feed them into GitHub code scanning, bringing familiar build-time security practices to a fast-growing part of the agent ecosystem.

“Constraining a model is harder than prompting one. Most of my work wasn't
  prompt engineering. It was building schema checks, rules against citing code
  that doesn't exist, and probe templates [GPT-5.6] can parameterize but never
  write.”



Sentinel was Bashaar’s first hackathon. He recently graduated with a computer science degree.

Learn more about the project and watch a demo [here](https://devpost.com/software/sentinel-way5bd). Or, [give it a try.](https://github.com/BashaarJavaid/MCP-Sentinel)

### Developer Tools Finalists

-  [Emberframe Studio](https://devpost.com/software/emberflame-workshop) gives developers a spatial canvas for building with AI agents.

-  [GenUI](https://devpost.com/software/genui-28s4hy) turns model-authored JSON into validated, native SwiftUI.

-  [Vibe Signal](https://devpost.com/software/vibe-signal) lets people monitor and steer Codex from an iPhone or Apple Watch.

## Education

### First-place: Mechanica

**Built by:** Weiying Zhu, Yukun Li, and Shan Wei

The idea for Mechanica began during a museum visit. “It's funny and embarrassing to say out loud, but I've hit my head on museum glass more times than I can count because I was too absorbed in the piece behind it,” shared Shan Wei.

The team wanted to be able to do more than look at a machine on display - they wanted to operate it, pull it apart, and understand how it worked. Or, as Yukun Li put it: “a way to see and feel a culture more closely.”

Mechanica turns fragmentary historical records into working, interactive reconstructions of four ancient Chinese machines, from an astronomical clock tower to a programmable loom created centuries before modern computing. Visitors can operate the mechanisms, pull them apart, and trace every dimension back to a classical text, measured artifact, or clearly labeled scholarly inference.

Some ancient machines survive largely as a few lines of text, making it difficult to picture how they may have moved. Where historians disagree, Mechanica presents competing reconstructions instead of pretending there is one definitive answer.

The three builders had decades of software experience, but little or no experience with 3D modeling, animation, physics simulation, or hackathons. Codex helped the team move into unfamiliar territory across 3D modeling, physics, and animation, while GPT-5.6 powers an AI docent designed to cite the museum’s evidence or decline to answer when the evidence is not there.

“The limit really is my imagination. I’ve written software for 25 years, but
  3D and animation were completely outside my lane, and that barrier is simply
  gone now. People can build far beyond their own specialty.” – Weiying Zhu



Learn more about the project and watch the demo [here](https://devpost.com/software/xiaoqiang). Or, [visit the digital museum](https://mechanica-museum.vercel.app/).

### Second-place: Dấu

**Built by:** Robert Huynh

Robert Huynh had participated in one hackathon before Build Week—but left after half a day because he worried he was not “technical enough” to belong. During Build Week, he showed up alone in Hanoi and built Dấu, a visual coach for one of the hardest parts of learning Vietnamese: tones.

Robert grew up in a Vietnamese-speaking family familiar with the common frustration of saying a word, hearing everyone laugh, and not knowing what your tone changed.

In Vietnamese, the same syllable can carry six different meanings depending on its pitch and vocal quality. Dấu makes those differences visible. Learners record a word, see their pitch curve beside a validated native-speaker reference, learn what meaning their pronunciation may have produced, and receive a specific physical correction.

One of Robert’s most important technical decisions was deciding what AI should not do. Deterministic signal processing evaluates the tone, and GPT‑5.6 coaches the learner. When the evidence is unclear, Dấu asks the learner to try again rather than confidently giving the wrong answer.

“I went from wondering if I was technical enough to belong at a hackathon to
  having something I built solo become a finalist. AI is making it possible for
  way more people to become builders, and you don’t need to wait until you feel
  technical enough to do the thing.” – Robert Huynh



Learn more about the project and watch the demo [here](https://devpost.com/software/d-u-see-your-vietnamese-tones). Or, [give it a try.](https://dau.huynhrobert.com/)

### Education Finalists

-  [Canopy](https://devpost.com/software/canopy-m01bog) asks learners to apply what AI teaches them in a coding sandbox.

-  [Encore!](https://devpost.com/software/encore-every-mistake-gets-an-encore) turns mistakes on a child’s test into personalized storybook lessons.

-  [ResearchOS](https://devpost.com/software/researchos-ze8so5) makes every research claim traceable to its source.

## Thank you!

Thanks to all the builders, event participants, and Codex ambassadors who brought this global celebration of building to life. To keep in touch with what’s happening for developers at OpenAI, keep an eye on our [developers page](https://developers.openai.com/) and, to stay connected in person, [attend a community event near you](https://developers.openai.com/community/meetups).