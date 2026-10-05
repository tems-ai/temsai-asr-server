# Commercial License for Official Images

The source code of temsai-asr-server is, and stays, licensed under the
[Apache License 2.0](LICENSE). This document does not change that.

In this document, "Tems.AI" means TemsSoft B.V., the company that develops
Tems.AI and grants the commercial licenses described here.

It covers the **Official Images**, the container images that Tems.AI builds
and distributes starting with version **0.2.0**, and every **Derived Image**
made from them. Images you build yourself from the source code are not covered
by it.

## 1. Definitions

- **Official Images**: container images built and published by Tems.AI,
  including `ghcr.io/tems-ai/temsai-asr-server` and any other registry or
  archive Tems.AI distributes them from, version 0.2.0 or later. They carry the
  label `org.opencontainers.image.vendor="Tems.AI"` and an
  `org.opencontainers.image.licenses` value that includes
  `LicenseRef-TemsAI-Commercial`.
- **Derived Images**: images that contain an Official Image or any of its
  layers, for example images built `FROM` an Official Image, and copies of an
  Official Image that are modified, re-tagged, mirrored, exported or
  re-packaged.
- **Self-built Images**: images you build yourself from the source code in this
  repository or a fork of it, for example with `docker build .`, without
  using any Official Image or its layers.
- **Commercial Use**: any use by or for a company, government body or other
  organisation in production, or to process data as part of its business,
  including providing services to third parties. Evaluation, development,
  testing, CI, demos and proofs of concept are not Commercial Use.
- **Production Host**: a physical server or virtual machine on which an
  Official Image runs, or may be scheduled to run, for Commercial Use, counted
  as set out in section 4.

## 2. Free use

You may use the Official Images free of charge for:

- personal and non-commercial use;
- education and academic research;
- evaluation, development, testing, CI and proofs of concept, for any
  organisation and without time limit, as long as they do not serve production
  traffic.

## 3. Commercial Use requires a license

Commercial Use of the Official Images requires a paid commercial license from
Tems.AI. To buy one, write to **support@tems.ai**.

The license is a subscription. It entitles you to run the Official Images for
Commercial Use on up to the licensed number of Production Hosts during the
subscription term, and to receive updated Official Images (security fixes, new
releases) during that term.

## 4. How Production Hosts are counted

The license is sized by the **maximum number of Production Hosts at any time**
during the subscription term:

- **Kubernetes**: every node of each production cluster on which the Official
  Images run counts. If you restrict the Official Images to a dedicated node
  pool (with node selectors, affinity rules or taints and tolerations), only
  the nodes of that pool count. Autoscaling counts at its peak node count.
- **Docker and other container runtimes outside Kubernetes**: every host that
  runs at least one Official Image counts.
- Every virtual machine counts as one host. Several containers or replicas on
  the same host count once.
- Hosts used only for evaluation, development, testing or CI do not count.

If you exceed the licensed number, tell us at support@tems.ai and we will
adjust the license for the rest of the term.

## 5. Derived Images and redistribution

Derived Images are covered by this license in the same way as the Official
Images they are made from: sections 2 to 4 apply to them, including the
commercial license requirement for Commercial Use.

You may store Official and Derived Images in your own private registries for
your own use. If you make a Derived Image available to the public or to third
parties (for example on Docker Hub, a public registry or a download page):

- it must be distributed under this Commercial License, and stated as such;
- the labels `org.opencontainers.image.vendor` and
  `org.opencontainers.image.licenses` and the `/licenses` directory from the
  Official Image must be kept unchanged;
- you may not grant its recipients any rights beyond those in this document,
  and Commercial Use by them requires their own commercial license from
  Tems.AI.

Redistributing an unmodified Official Image is subject to the same conditions.

## 6. Self-built Images

Images you build yourself from the source code are licensed under the Apache
License 2.0 only, and this document does not apply to them. You may use them
for any purpose, including Commercial Use, free of charge, and you may
redistribute them under the Apache License 2.0. Tems.AI does not provide
support or updates for them.

If you make a Self-built Image available to the public, section 8 applies: it
must not use the Tems.AI name in its image name, tags or vendor label, so that
it cannot be confused with an Official Image.

Images published by Tems.AI before version 0.2.0 were released under the
Apache License 2.0 and remain under it.

## 7. Third-party components

The Official Images contain third-party software and model weights that are
licensed under their own terms, listed in [NOTICE](NOTICE) and shipped in each
image under `/licenses`, among them FFmpeg (GPL/LGPL), PyTorch (BSD-3-Clause),
NVIDIA NeMo (Apache-2.0) and, in images with the model built in, the NVIDIA
Parakeet-TDT weights (CC BY 4.0). This license applies only to the components
created by Tems.AI and to the Official and Derived Images as compiled wholes. It does not
restrict any right you have to a third-party component under its own license.

## 8. Trademarks

"Tems.AI" and the Tems.AI logo are trademarks of Tems.AI. Neither the Apache
License 2.0 nor this document grants permission to use them. You may refer to
the project by name to describe it truthfully ("built from the
temsai-asr-server source code"), but a Self-built or modified image must not be
presented as an Official Image or as provided by Tems.AI. Publicly distributed
Self-built Images must not use "Tems.AI", "TemsAI" or "temsai" in their image
name, tags or `org.opencontainers.image.vendor` label.

## 9. No warranty

Unless your commercial license agreement says otherwise, the Official and
Derived Images are provided "AS IS", without warranties or conditions of any kind, as set out
in sections 7 and 8 of the Apache License 2.0.

## Security and compliance

TemsSoft B.V. is certified to ISO/IEC 27001 for its information security
management system. Certificate details are available to customers on request
at support@tems.ai.

## Contact

Licensing, pricing and support: **support@tems.ai**
