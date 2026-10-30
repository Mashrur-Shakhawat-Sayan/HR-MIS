# Changelog

## 1.1.1 — any-company release

- The demo organisation is now **Sonar Tori Group**, a fictional conglomerate. Demo employee IDs are `ST-1001` onwards.
- A fresh install (`--empty`) starts neutral: company name "Your Company" and ID prefix `EMP-`, both set in **Settings**.
- README and overview explain that HR-MIS fits any group or large company (for example Meghna Group, Akij Group, United Group or Grameenphone) without code changes.
- New **push-to-github.bat**: one click signs in to GitHub, creates the repository if needed and uploads everything except the `data` folder.

## 1.1.0 — bug-fix and redesign release

### Fixed
| Area | Problem | Fix |
|---|---|---|
| Server (critical) | When a button sent a request whose body the server didn't need (Finalize, Mark as paid, Reopen, Cancel leave, Sign out, …), the unread bytes stayed on the browser's keep-alive connection and corrupted the **next** request, which failed with HTTP 501 ("Request failed"). This showed up as random failures in payroll, settings, leave and self-service. | Every request body is now always read before routing (`core/http.py → read_body`). Oversized bodies close the connection. Regression test `test_70`. |
| Privacy | Line managers could open **every** employee's profile (date of birth, address, emergency contact, parents' names). | Managers now see only themselves and their direct reports. The employee list, profiles and search are all scoped on the server (`test_71`). |
| Lifecycle | An employee who resigned with a future last working day stayed "On Notice" for ever, kept appearing in daily attendance and payroll, and kept their login. | A daily job finalises the status (Resigned / Terminated / Retired) the day after the last working day and disables the login. Attendance and payroll eligibility now respect exit dates (`test_73`). |
| Data integrity | Reporting lines could form a loop (A reports to B, B reports to A), which hid both people from the org chart. | Loops are refused when editing an employee or recording a transfer (`test_72`). |
| Accounts | An administrator could demote or disable themselves, or the last administrator, and lock everyone out of user management. | Both are refused (`test_74`). |
| Payroll | A **half-day** unpaid leave was deducted as a full day. | It now counts as half a day. |
| Attendance | "Mark the rest present" worked for future dates. | Refused; future dates accept only leave, remote work or on-duty (`test_76`). |
| Notices | Employees saw expired notices on the notice board. | Hidden from employees; HR still sees them (`test_77`). |
| Security | CSV exports could carry spreadsheet formulas typed into a field (`=HYPERLINK(...)`), which Excel would run. | Text cells starting with `= + - @` are neutralised (`test_75`). |
| Security | A static-file path check could be bypassed by a sibling folder name; uploaded file names with characters Windows forbids could fail; Bangla file names broke downloads. | Path containment by `commonpath`; upload extensions sanitised; downloads send an ASCII name plus the UTF-8 name. |
| Sign-in | The "choose a new password" dialog for new accounts could be dismissed with Esc or Cancel. | It is locked until a new password is saved. |
| UI | "My profile" appeared for accounts without an employee record and silently went nowhere. The Employees "Export" button appeared for managers who can't run reports. The "Any status" filter actually showed active staff only. In western time zones My Attendance showed the wrong weekday. Handled validation errors were logged as browser errors. | All fixed. |

### Redesigned
- New visual identity: bottle green from the national flag for navigation and actions, marigold only for things that need attention, flag red only for destructive actions.
- Bundled fonts (no internet needed): **Instrument Sans** for the interface and **Bricolage Grotesque** for titles and headline figures, both under the SIL Open Font License (`frontend/fonts/`).
- About 60 original line icons replace emoji (`frontend/js/core/icons.js`).
- Headline figures in one ruled "ledger" strip; attendance register as coloured status tiles.
- **Dark mode** that follows Windows or can be switched from the top bar (the choice is remembered).
- **Search palette:** press **Ctrl + K** (or `/`) to jump to any page or employee.
- New sign-in page: select a demo account to fill the form.
- Page headers with back links, a clearer form layout, empty states, plain-language messages ("3 claims" rather than "3 claim(s)"), keyboard focus rings and reduced-motion support.
- Payslips and printouts always render as white paper, whatever the theme.

### Testing
- `tests/e2e_features.py`: a browser test that signs in as every role and uses every feature (create, edit, delete, approve, upload, export and print), failing on any browser error, failed server call or error message. 28 steps.
- `tests/test_api.py` grew from 17 to 25 tests with regression tests for every fix above.

## 1.0.0
First release: 15 modules, six roles, payroll, self-service, 17 reports and full documentation.
