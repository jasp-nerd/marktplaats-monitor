# Third-Party Notices

This project is not a runtime consumer of any third-party Marktplaats client.
However, two small, stable, high-effort-to-reproduce pieces of logic are
**vendored** (copied and adapted) into this codebase under the terms of the
MIT License:

1. The Marktplaats **L1/L2 category ID ↔ name map** and category lookup
   helpers — see `marktplaats_monitor/categories.py`.
2. The **Dutch relative-date parser** and **price-type mapping** — see the
   clearly marked vendored sections of `marktplaats_monitor/parsing.py`.

## Source

- Project: **marktplaats-py**
- Repository: https://github.com/jensjeflensje/marktplaats-py
- Vendored from: **v0.4.0** (default branch `main`, as of 2026-05-11)
- Refresh policy: vendored code is updated manually; bump the version above
  when re-syncing and re-check the upstream license.

## License of the vendored code

```
MIT License

Copyright (c) 2023 Jens de Ruiter

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
