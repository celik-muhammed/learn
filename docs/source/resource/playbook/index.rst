:orphan:
..
  # This file is included. So it needs to be marked as orphan to suppress warnings.
  # https://www.sphinx-doc.org/en/master/usage/restructuredtext/field-lists.html#metadata
  .. include:: dependencies.rst
      :start-after: :orphan:

.. contents:: On this page
   :local:
   :depth: 2

.. _resource-playbook-index:

==========================
Playbook
==========================

.. important:: External resources: useful references, not endorsements

   We share these external resources to help you explore and learn—not as
   endorsements. Their inclusion does not mean that scikit-plots has reviewed or
   verified the content, agrees with its claims or opinions, or sponsors or is
   affiliated with its creator. External material is maintained by its publisher
   and may change. Use your judgment, and check important claims, code, and setup
   or security advice against current official documentation before relying on it.

------------------------------------
Reliability & Incident Investigation
------------------------------------

On-Call & Alert Playbooks
^^^^^^^^^^^^^^^^^^^^^^^^^

* `Google SRE Workbook: What It Means Being On-Call?
  <https://sre.google/workbook/on-call/>`_
  (covers alert-driven playbooks, on-call handoffs, MTTR reduction, and keeping playbooks current)
  by Google SRE

* `AWS Well-Architected: Use Playbooks to Investigate Failures (REL12-BP01)
  <https://docs.aws.amazon.com/wellarchitected/latest/framework/rel12-bp01.html>`_
  (covers structured failure investigation, detection-to-recovery steps, and automating playbooks as code)
  by Amazon Web Services (AWS)

* `AWS Well-Architected: Develop and Test Playbooks to Respond to Incidents (OPS05-BP02)
  <https://docs.aws.amazon.com/wellarchitected/latest/framework/ops05-bp02.html>`_
  (covers playbook templates, outside-in discovery steps, escalation plans, and peer validation)
  by Amazon Web Services (AWS)

------------------------------------
LLM & Distributed Training Playbooks
------------------------------------

GPU Cluster Scaling & Training
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* `The Ultra-Scale Playbook: Training LLMs on GPU Clusters
  <https://huggingface.co/spaces/nanotron/ultrascale-playbook>`_
  (covers memory breakdowns, ZeRO/FSDP and tensor/pipeline parallelism, gradient overlap, and throughput tuning)
  by Hugging Face / Nanotron

-------------------------------------
Risk, Governance & Security Playbooks
-------------------------------------

AI Risk & Incident Response
^^^^^^^^^^^^^^^^^^^^^^^^^^^

* `NIST AI Risk Management Framework (AI RMF) Playbook
  <https://airc.nist.gov/airmf-resources/playbook/>`_
  (covers voluntary actionable guidance across Govern, Map, Measure, and Manage functions)
  by National Institute of Standards and Technology (NIST)

* `NIST SP 800-61r3: Incident Response Recommendations and Considerations
  <https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-61r3.pdf>`_
  (covers cybersecurity incident response playbooks, roles, and CSF 2.0 lifecycle alignment)
  by National Institute of Standards and Technology (NIST)
