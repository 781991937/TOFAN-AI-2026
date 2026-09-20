# TOFAN AI Detailed Course Delivery Map v1

This document turns `docs/curricula/ai_tofan_curriculum_v1.json` into an executable teaching map.
TOFAN uses prerequisites and demonstrated outcomes, not university semester labels, as the primary progression mechanism.

## Delivery standard

Every lesson follows:
1. Concept introduction from zero.
2. Terminology before use.
3. Worked example.
4. Guided application.
5. Understanding check.
6. Student confirmation of understanding.
7. Practice task.
8. Evidence of mastery.

Every course follows:
- Diagnostic entry check.
- Units in prerequisite order.
- Lesson-level understanding checks.
- Practical assignment(s).
- Course assessment.
- Mastery review for failed outcomes.
- Course completion only when required outcomes are evidenced.

## Course maps

### AI-FND-001 — مهارات الحاسوب والبيئة الرقمية
Prerequisites: none
Units:
1. البيئة الرقمية: hardware/software, OS, files and folders.
2. أدوات العمل: browser, editor/IDE, terminal, package basics.
3. إدارة المشاريع: paths, extensions, archives, backups, workspace organization.
4. Developer readiness: environment setup, troubleshooting, safe downloads.
Assessment: practical environment setup and file-management task.

### AI-FND-002 — التفكير الحاسوبي وحل المشكلات
Prerequisites: none
Units:
1. Problem decomposition: inputs, outputs, constraints, edge cases.
2. Algorithms: sequences, decisions, repetition, abstraction.
3. Pseudocode and flowcharts: translating requirements into procedures.
4. Solution analysis: alternatives, correctness, efficiency, testing.
Assessment: analyze and algorithmically solve three unfamiliar problems.

### AI-FND-003 — اللغة الإنجليزية التقنية
Prerequisites: none
Units:
1. Core computing vocabulary.
2. Reading code, errors, commands and documentation.
3. Technical search and information extraction.
4. Writing short technical explanations and reports.
Assessment: read a technical document and produce an accurate explanation.

### AI-FND-004 — مهارات التواصل والعمل التقني
Prerequisites: none
Units:
1. Technical communication fundamentals.
2. Technical writing and documentation.
3. Presentation and explanation of technical ideas.
4. Team communication, feedback and project reporting.
Assessment: written technical report + short project presentation.

### AI-PRG-101 — أساسيات البرمجة باستخدام Python
Prerequisites: AI-FND-002
Units:
1. Python execution, variables, types, input/output, operators.
2. Conditions, Boolean logic and repetition.
3. Strings, lists, tuples, sets and dictionaries.
4. Functions, modules, exceptions, files and small programs.
Assessment: build, test and debug a small Python application.

### AI-PRG-102 — البرمجة الكائنية وهندسة الكود
Prerequisites: AI-PRG-101
Units:
1. Functions, modules and program structure.
2. Classes, objects, attributes and methods.
3. Encapsulation, inheritance and polymorphism.
4. Refactoring, reusable components, exceptions and testing.
Assessment: modular OOP application with tests.

### AI-PRG-103 — Git وGitHub وإدارة الإصدارات
Prerequisites: AI-PRG-101
Units:
1. Git model, repository and working tree.
2. Commit, history, diff, restore and branching.
3. Merge, conflict resolution and remote repositories.
4. GitHub workflow, issues, pull requests and project documentation.
Assessment: publish and manage a complete versioned project.

### AI-CS-104 — أساسيات الأنظمة والحوسبة
Prerequisites: AI-FND-001
Units:
1. CPU, memory, storage and buses.
2. Operating-system concepts, processes and files.
3. Programs, runtime environments and resource management.
4. Computing environments for AI: local, cloud and accelerated hardware.
Assessment: explain and diagnose a simple computing environment.

### AI-MATH-201 — الرياضيات المتقطعة والمنطق
Prerequisites: AI-FND-002
Units:
1. Propositions, predicates and logical operators.
2. Sets, relations and functions.
3. Proof, induction and logical inference.
4. Graphs, trees and discrete structures.
Assessment: solve logic, set, relation and graph problems.

### AI-MATH-202 — الجبر الخطي للذكاء الاصطناعي
Prerequisites: AI-FND-002
Units:
1. Scalars, vectors and vector operations.
2. Matrices, matrix operations and linear systems.
3. Transformations, basis, rank and geometric interpretation.
4. Eigenvalues/eigenvectors and AI applications.
Assessment: solve linear-algebra problems and implement core operations in Python.

### AI-MATH-203 — التفاضل والتكامل للذكاء الاصطناعي
Prerequisites: AI-FND-002
Units:
1. Functions, limits and derivatives.
2. Partial derivatives and multivariable functions.
3. Gradient, chain rule and optimization.
4. Derivatives in loss minimization and neural networks.
Assessment: derive and solve optimization examples relevant to ML.

### AI-MATH-204 — الاحتمالات والإحصاء للذكاء الاصطناعي
Prerequisites: AI-MATH-201
Units:
1. Probability spaces, events and conditional probability.
2. Bayes theorem and random variables.
3. Distributions, expectation, variance and sampling.
4. Descriptive statistics, correlation and statistical interpretation.
Assessment: analyze a dataset and solve probability/statistics cases.

### AI-ALG-205 — هياكل البيانات والخوارزميات
Prerequisites: AI-PRG-102, AI-MATH-201
Units:
1. Complexity and Big-O.
2. Arrays, linked structures, stacks and queues.
3. Trees, heaps, hash tables and graphs.
4. Searching, sorting and algorithm selection.
Assessment: implement and compare data structures and algorithms.

### AI-DATA-206 — قواعد البيانات وSQL
Prerequisites: AI-PRG-102
Units:
1. Data models, entities, attributes and relationships.
2. Relational databases, keys and normalization basics.
3. SQL queries, joins, aggregation and constraints.
4. Data preparation and database access from Python.
Assessment: design and implement a database-backed mini application.

### AI-CORE-301 — مقدمة في الذكاء الاصطناعي
Prerequisites: AI-PRG-101, AI-MATH-201
Units:
1. AI definitions, history overview, AI vs ML vs DL.
2. Intelligent behavior, rationality and agent concepts.
3. Task environments, PEAS, observability, determinism, dynamics.
4. Agent types, learning agents, applications, impact and ethics.
Assessment: analyze unfamiliar environments and design rational agents.

### AI-CORE-302 — تمثيل المشكلات والبحث
Prerequisites: AI-CORE-301, AI-ALG-205
Units:
1. Problem formulation and state-space representation.
2. Breadth-first and depth-first search.
3. Uniform-cost and depth-limited search.
4. Search comparison, completeness, optimality and complexity.
Assessment: formulate and solve multiple search problems.

### AI-CORE-303 — البحث الاستدلالي وتحسين الحلول
Prerequisites: AI-CORE-302
Units:
1. Heuristics and informed search.
2. Greedy Best-First Search.
3. A* and path-cost/heuristic interaction.
4. Admissibility, consistency and search evaluation.
Assessment: design heuristics and compare informed-search strategies.

### AI-CORE-304 — تمثيل المعرفة والاستدلال
Prerequisites: AI-CORE-301, AI-MATH-201
Units:
1. Knowledge bases, facts and rules.
2. Propositional logic representation.
3. Inference, forward chaining and backward chaining.
4. First-order concepts and limitations of symbolic representation.
Assessment: build a rule-based knowledge system.

### AI-CORE-305 — الاستدلال الاحتمالي واتخاذ القرار
Prerequisites: AI-MATH-204, AI-CORE-304
Units:
1. Uncertainty in AI.
2. Bayesian reasoning.
3. Probabilistic models and conditional independence.
4. Decision making under uncertainty.
Assessment: construct and explain a probabilistic decision model.

### AI-ML-401 — أساسيات تعلم الآلة
Prerequisites: AI-CORE-301, AI-MATH-202, AI-MATH-204, AI-PRG-102
Units:
1. ML problem types and datasets.
2. Features, labels, training, validation and test.
3. Supervised, unsupervised and reinforcement learning.
4. ML workflow, baseline models and experiment discipline.
Assessment: complete an end-to-end introductory ML workflow.

### AI-ML-402 — معالجة البيانات وتحليلها
Prerequisites: AI-DATA-206, AI-MATH-204, AI-PRG-102
Units:
1. Data acquisition and inspection.
2. Missing values, duplicates and inconsistent data.
3. Encoding, scaling and feature preparation.
4. Exploratory analysis and dataset quality.
Assessment: turn a raw dataset into a training-ready dataset.

### AI-ML-403 — التعلم الخاضع للإشراف
Prerequisites: AI-ML-401, AI-ML-402
Units:
1. Regression and prediction.
2. Classification and decision boundaries.
3. Linear/logistic regression, KNN and trees.
4. Training, tuning and interpretation.
Assessment: solve a regression and classification problem.

### AI-ML-404 — التعلم غير الخاضع للإشراف
Prerequisites: AI-ML-401, AI-ML-402
Units:
1. Clustering problem formulation.
2. K-Means and cluster evaluation.
3. Hierarchical clustering and alternatives.
4. Dimensionality reduction and PCA.
Assessment: discover and explain structure in unlabeled data.

### AI-ML-405 — تقييم النماذج وتحسينها
Prerequisites: AI-ML-403
Units:
1. Confusion matrix and classification metrics.
2. Regression metrics.
3. Overfitting, underfitting, bias and variance.
4. Cross-validation, regularization and model comparison.
Assessment: produce a defensible model evaluation report.

### AI-ML-406 — التعلم المعزز
Prerequisites: AI-ML-401, AI-MATH-204, AI-CORE-303
Units:
1. Agent, environment, state, action and reward.
2. Policies and value concepts.
3. Q-learning.
4. Exploration, exploitation and evaluation.
Assessment: implement a small reinforcement-learning environment.

### AI-DL-501 — الشبكات العصبية
Prerequisites: AI-ML-405, AI-MATH-202, AI-MATH-203
Units:
1. Neurons, weights, bias and activation functions.
2. Forward propagation and loss.
3. Gradient descent and backpropagation.
4. Training, validation and diagnosis.
Assessment: implement and train a simple neural network.

### AI-DL-502 — التعلم العميق التطبيقي
Prerequisites: AI-DL-501
Units:
1. Deep architectures and training workflow.
2. Optimization and regularization.
3. CNN/RNN architectural concepts.
4. Training diagnosis and experiment design.
Assessment: train and compare deep models on a real dataset.

### AI-DL-503 — PyTorch وهندسة نماذج التعلم العميق
Prerequisites: AI-DL-501, AI-PRG-103
Units:
1. Tensors and datasets.
2. DataLoader, model and forward pass.
3. Loss, optimizer and training loop.
4. Checkpoints, inference, evaluation and reproducibility.
Assessment: build a documented PyTorch project.

### AI-VIS-601 — الرؤية الحاسوبية
Prerequisites: AI-DL-502, AI-DL-503
Units:
1. Image representation and preprocessing.
2. CNN-based image classification.
3. Object detection concepts.
4. Segmentation, embeddings and evaluation.
Assessment: deliver an evaluated computer-vision application.

### AI-NLP-602 — معالجة اللغة الطبيعية
Prerequisites: AI-DL-502, AI-ML-402
Units:
1. Text representation and preprocessing.
2. Tokenization and embeddings.
3. Sequence models and attention concepts.
4. NLP tasks and evaluation.
Assessment: build and evaluate an NLP application.

### AI-AGT-603 — الوكلاء الأذكياء والأنظمة متعددة الوكلاء
Prerequisites: AI-CORE-301, AI-ML-401, AI-CORE-303
Units:
1. Agent architectures and autonomy.
2. Reactive, goal-based, utility-based and learning agents.
3. Agent communication and multi-agent interaction.
4. Evaluation, coordination and failure handling.
Assessment: implement an agent operating in a defined environment.

### AI-PLAN-604 — التخطيط وحل المشكلات
Prerequisites: AI-CORE-302, AI-CORE-304
Units:
1. Planning problems and representations.
2. States, actions, goals and preconditions.
3. Plan generation and search.
4. Planning under uncertainty and comparison with search.
Assessment: formulate and solve a planning problem.

### AI-ROB-605 — الروبوتات والذكاء المتجسد
Prerequisites: AI-AGT-603, AI-CORE-303
Units:
1. Robot architecture, sensors and actuators.
2. Perception and environment interaction.
3. Localization and motion/planning concepts.
4. Decision-making for embodied agents.
Assessment: simulate or prototype a robot decision system.

### AI-GEN-701 — النماذج التوليدية والذكاء الاصطناعي التوليدي
Prerequisites: AI-DL-502, AI-NLP-602
Units:
1. Generative vs predictive modeling.
2. Text, image and audio generation concepts.
3. Prompting, conditioning and evaluation.
4. Building applications with pretrained generative models.
Assessment: create and evaluate a constrained GenAI application.

### AI-LLM-702 — النماذج اللغوية الكبيرة وTransformers
Prerequisites: AI-NLP-602, AI-DL-502
Units:
1. Tokenization and embeddings.
2. Attention and Transformer architecture.
3. Pretraining, fine-tuning and instruction tuning.
4. LLM application patterns, context and evaluation.
Assessment: build an LLM application and document its limitations.

### AI-RAG-703 — RAG والبحث الدلالي وقواعد المتجهات
Prerequisites: AI-LLM-702, AI-DATA-206
Units:
1. Embeddings and semantic similarity.
2. Document ingestion and chunking.
3. Vector storage and retrieval.
4. RAG generation, citation grounding and evaluation.
Assessment: build a grounded document-questioning system.

### AI-AGT-704 — هندسة وكلاء الذكاء الاصطناعي
Prerequisites: AI-AGT-603, AI-LLM-702
Units:
1. Agent loops and tool use.
2. Planning, observation and action.
3. Memory, state and multi-agent orchestration.
4. Permissions, safety, evaluation and failure recovery.
Assessment: build a controlled tool-using agent.

### AI-MULTI-705 — الذكاء الاصطناعي متعدد الوسائط
Prerequisites: AI-VIS-601, AI-NLP-602, AI-LLM-702
Units:
1. Multimodal representations.
2. Vision-language models.
3. Audio/text/image integration.
4. Multimodal retrieval and agent applications.
Assessment: build a multimodal application and evaluate each modality.

### AI-ENG-801 — هندسة برمجيات أنظمة الذكاء الاصطناعي
Prerequisites: AI-PRG-103, AI-ML-401
Units:
1. AI system architecture and requirements.
2. APIs, services and model integration.
3. Testing, documentation and observability.
4. Maintainability, versioning and lifecycle.
Assessment: design and implement a production-style AI service.

### AI-ENG-802 — MLOps ونشر نماذج الذكاء الاصطناعي
Prerequisites: AI-ENG-801, AI-DL-503
Units:
1. Packaging and model serving.
2. Data/model versioning and pipelines.
3. CI/CD and deployment environments.
4. Monitoring, drift and rollback.
Assessment: deploy and monitor an ML service.

### AI-ENG-803 — أمن أنظمة الذكاء الاصطناعي
Prerequisites: AI-ENG-801, AI-AGT-704
Units:
1. AI threat model and attack surface.
2. Prompt injection and tool abuse.
3. Data poisoning and adversarial examples.
4. Identity, permissions, isolation and secure evaluation.
Assessment: threat-model and harden an AI agent/application.

### AI-ENG-804 — أخلاقيات وحوكمة الذكاء الاصطناعي
Prerequisites: AI-CORE-301
Units:
1. Bias, fairness and data quality.
2. Privacy and responsible data use.
3. Transparency, accountability and explainability.
4. Risk assessment, governance and human oversight.
Assessment: produce a responsible-AI risk and mitigation plan.

## Project progression

### AI-PROJ-901 — مشروع البرمجة
Prerequisites: AI-PRG-102, AI-PRG-103
Stages: requirements → design → implementation → testing → GitHub documentation → presentation.
Evidence: working application, tests, repository history and technical report.

### AI-PROJ-902 — مشروع تعلم الآلة
Prerequisites: AI-ML-405
Stages: problem → data → EDA → preprocessing → baseline → training → evaluation → interpretation.
Evidence: reproducible notebook/code, evaluation report and presentation.

### AI-PROJ-903 — مشروع التعلم العميق
Prerequisites: AI-DL-503
Stages: dataset → architecture → training → tuning → evaluation → error analysis → deployment demo.
Evidence: model, experiment log, metrics and technical report.

### AI-PROJ-904 — مشروع تخصصي
Prerequisites: at least one of AI-VIS-601, AI-NLP-602, AI-AGT-603 plus its required prerequisites.
Stages: domain problem → literature/solution review → design → implementation → evaluation → documentation.
Evidence: domain-specific working system.

### AI-PROJ-905 — مشروع الذكاء الاصطناعي التوليدي والوكلاء
Prerequisites: AI-RAG-703, AI-AGT-704, AI-ENG-803
Stages: use case → model selection → tools/RAG → agent loop → permissions → evaluation → deployment demo.
Evidence: controlled GenAI/Agent system with safety and evaluation documentation.

### AI-PROJ-906 — مشروع التخرج
Prerequisites: AI-ENG-802, AI-ENG-803, AI-ENG-804, AI-PROJ-904
Stages: proposal → requirements → research review → architecture → implementation → experiments → security/risk review → deployment → final defense.
Evidence: complete AI system, source code, documentation, evaluation, deployment/demo and defense.

## Course mastery gate

A course is not marked complete merely because lessons were viewed. The teacher agent must verify the required learning outcomes through explanation, application, problem solving and assessment. Failed outcomes trigger targeted remediation and reassessment.

## Weekly teaching template

Each active study day:
- Lecture/lesson 1: concept + guided application + mini-check.
- Lecture/lesson 2: concept + worked example + mini-check.
- Lecture/lesson 3: application + problem solving + mini-check.
- End-of-session: mastery record and next prerequisite-safe lesson.

The exact number of lessons per week is adaptive; it is not used as a substitute for mastery.
