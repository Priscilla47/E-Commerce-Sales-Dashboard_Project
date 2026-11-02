# Decision records

A decision record explains one choice that shapes the project: what the situation was, which options were considered, which one was chosen and what follows from it. They are written for the contributors of today and for whoever reads the code later and wonders "why this and not that?".

## Records

| Record | Title | Status |
|--------|-------|--------|
| [0001](0001-use-pandas.md) | Use pandas for the analytics | Accepted |
| [0002](0002-use-streamlit.md) | Use Streamlit for the dashboard | Accepted |

## The format

Every record is a file `NNNN-short-title.md`, numbered in the order it was written, with the title `# N. Title` and these five sections, always in this order:

| Section | What it holds |
|---------|---------------|
| **Status** | `Proposed`, `Accepted`, `Superseded` (by which record) or `Rejected`, with a short note if needed. |
| **Context** | The situation and the constraints that force a choice. Facts, not wishes. |
| **Options** | Each option considered under its own `###` heading, with what is good and bad about it. Say what was **ruled out** and why, and mark the one **chosen**. |
| **Decision** | What we do, in one or two sentences. |
| **Consequences** | What becomes easier and harder, and a paragraph that starts "When we would revisit it" with the facts that would make us change our mind. |

## Add a record

1. Copy the last record, give the new file the next number (`0003-...`) and write the five sections.
2. Add a row to the table above, with the same title and the status of the record.
3. Run `pytest tests/test_docs_decisions.py`: it checks the sections, the numbering, the index and the links.

A decision is never deleted or rewritten when it changes. Write a new record that says it supersedes the old one, and change the status of the old one to `Superseded by 000N`.
