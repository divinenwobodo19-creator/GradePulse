import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import EmptyState from "../EmptyState";

describe("EmptyState", () => {
  it("renders the heading, body, icon and action it is given", () => {
    const html = renderToStaticMarkup(
      <EmptyState
        icon={<svg data-icon="students" />}
        heading="No students found"
        body="Add your first student to get started"
        action={<button type="button">Add Student</button>}
      />
    );
    expect(html).toContain('data-testid="empty-state"');
    expect(html).toContain('<div class="empty-state-icon"><svg data-icon="students"></svg></div>');
    expect(html).toContain(">No students found</h3>");
    expect(html).toContain("Add your first student to get started");
    expect(html).toContain("<button");
    // Spacing under the body only when a button follows it.
    expect(html).toContain('class="body-sm text-text-muted mb-4"');
  });

  it("leaves out what it is not given", () => {
    const html = renderToStaticMarkup(<EmptyState heading="No classes yet" />);
    expect(html).toContain(">No classes yet</h3>");
    expect(html).not.toContain("empty-state-icon");
    expect(html).not.toContain("<p");
    expect(html).not.toContain("<button");
  });

  it("does not add spacing under the body when there is no action", () => {
    const html = renderToStaticMarkup(<EmptyState heading="Select a student" body="Choose a student" />);
    expect(html).toContain('class="body-sm text-text-muted">Choose a student</p>');
  });
});
