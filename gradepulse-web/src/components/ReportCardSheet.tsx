// One student's end-of-term report card, laid out to print on one A4 page.
import { formatMark, gradeKey, longDate, ordinal } from "@/lib/reportCards";
import type { ReportCard, ReportCardsResponse } from "@/lib/types";

export default function ReportCardSheet({ data, card }: { data: ReportCardsResponse; card: ReportCard }) {
  const { term, school, settings, class_size } = data;
  const positions = settings.show_positions;

  return (
    <section className="card report-sheet report-card">
      <div className="card-body">
        <header className="text-center border-b-2 border-navy pb-3 mb-4">
          <div className="heading-1 text-navy uppercase tracking-wide">{school.name}</div>
          {school.address && <div className="body-sm text-text-secondary">{school.address}</div>}
          <div className="caption font-semibold uppercase tracking-wider text-text-secondary mt-2">
            Term report card · {term.name} · {term.session} session
          </div>
        </header>

        <dl className="report-card-facts">
          <div><dt>Name</dt><dd className="font-semibold">{card.name}</dd></div>
          <div><dt>Student ID</dt><dd>{card.student_id}</dd></div>
          <div><dt>Class</dt><dd>{data.class.label}</dd></div>
          <div><dt>No. in class</dt><dd>{class_size}</dd></div>
          <div>
            <dt>Attendance</dt>
            <dd>
              {card.days_present === null ? "—" : card.days_present}
              {term.days_opened > 0 && ` of ${term.days_opened} days`}
            </dd>
          </div>
          {positions && (
            <div>
              <dt>Position in class</dt>
              <dd className="font-semibold">{card.position === null ? "—" : `${ordinal(card.position)} of ${class_size}`}</dd>
            </div>
          )}
        </dl>

        {card.subjects.length === 0 ? (
          <p className="body-sm text-text-muted my-6">No marks have been recorded for this student this term.</p>
        ) : (
          <table className="report-table report-card-table">
            <thead>
              <tr>
                <th scope="col">Subject</th>
                <th scope="col" className="num">CA<br /><span className="font-normal">({settings.ca_weight})</span></th>
                <th scope="col" className="num">Exam<br /><span className="font-normal">({settings.exam_weight})</span></th>
                <th scope="col" className="num">Total<br /><span className="font-normal">(100)</span></th>
                <th scope="col">Grade</th>
                {positions && <th scope="col" className="num">Pos.</th>}
                <th scope="col" className="num">Class avg.</th>
                <th scope="col" className="num">High</th>
                <th scope="col" className="num">Low</th>
                <th scope="col">Remark</th>
              </tr>
            </thead>
            <tbody>
              {card.subjects.map((row) => (
                <tr key={row.subject}>
                  <th scope="row">{row.subject}</th>
                  <td className="num">{formatMark(row.ca)}</td>
                  <td className="num">{formatMark(row.exam)}</td>
                  <td className="num font-semibold">{formatMark(row.total)}</td>
                  <td>{row.grade || "—"}</td>
                  {positions && <td className="num">{row.position === null ? "—" : ordinal(row.position)}</td>}
                  <td className="num">{formatMark(row.class_average)}</td>
                  <td className="num">{formatMark(row.highest)}</td>
                  <td className="num">{formatMark(row.lowest)}</td>
                  <td>{row.teacher_remark || row.grade_remark || ""}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row" colSpan={3}>Total marks · Average</th>
                <td className="num font-semibold">{formatMark(card.total)}</td>
                <td colSpan={positions ? 6 : 5} className="font-semibold">
                  {card.average === null ? "—" : `Average ${formatMark(card.average)}%`}
                  {card.missing.length > 0 && card.average !== null && (
                    <span className="font-normal text-text-secondary">
                      {" "}({card.subjects.length - card.missing.length} of {card.subjects.length} subjects)
                    </span>
                  )}
                </td>
              </tr>
            </tfoot>
          </table>
        )}

        <p className="caption text-text-muted mt-2 report-card-key">
          Grades:{" "}
          {gradeKey(settings.grade_scale).map((band, i) => (
            <span key={band.grade}>
              {i > 0 && " · "}
              <strong>{band.grade}</strong> {band.range}
              {band.remark && ` ${band.remark}`}
            </span>
          ))}
        </p>

        <div className="report-card-comments">
          <div>
            <div className="caption font-semibold uppercase tracking-wider text-text-secondary">Form teacher&apos;s comment</div>
            <p className="body-sm min-h-[2.5rem]">{card.form_teacher_comment}</p>
            <div className="report-card-sign">Signature</div>
          </div>
          <div>
            <div className="caption font-semibold uppercase tracking-wider text-text-secondary">Principal&apos;s comment</div>
            <p className="body-sm min-h-[2.5rem]">{card.principal_comment}</p>
            <div className="report-card-sign">{school.principal_name || "Principal"} · Signature &amp; stamp</div>
          </div>
        </div>

        <footer className="flex justify-between items-end mt-5 caption text-text-secondary">
          <div>
            {term.next_term_begins && (
              <span className="font-semibold text-navy">Next term begins: {longDate(term.next_term_begins)}</span>
            )}
          </div>
          <div className="text-right text-text-muted">GradePulse · gradepulse.com.ng</div>
        </footer>
      </div>
    </section>
  );
}
