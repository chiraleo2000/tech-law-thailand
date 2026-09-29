import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { toBuddhistDate, sortPosts } from "../js/utils.js";
import { renderPost } from "../js/renderer.js";

const isoDate = fc
  .record({
    year: fc.integer({ min: 2000, max: 2100 }),
    month: fc.integer({ min: 1, max: 12 }),
    day: fc.integer({ min: 1, max: 28 }),
  })
  .map(({ year, month, day }) => `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`);

describe("blog rendering", () => {
  it("Property 8: sortPosts orders by announcement date then Thai title", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            announcement_date: isoDate,
            title: fc.string({ minLength: 1, maxLength: 20 }),
            id: fc.string({ minLength: 1, maxLength: 8 }),
          }),
          { maxLength: 30 },
        ),
        (posts) => {
          const sorted = sortPosts(posts);
          for (let index = 1; index < sorted.length; index += 1) {
            const previous = sorted[index - 1];
            const current = sorted[index];
            expect(previous.announcement_date >= current.announcement_date).toBe(true);
            if (previous.announcement_date === current.announcement_date) {
              expect(previous.title.localeCompare(current.title, "th") <= 0).toBe(true);
            }
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it("Property 9: toBuddhistDate adds 543 to the year", () => {
    fc.assert(
      fc.property(isoDate, (iso) => {
        const [year, month, day] = iso.split("-").map(Number);
        expect(toBuddhistDate(iso)).toBe(`${day}/${month}/${year + 543}`);
      }),
      { numRuns: 100 },
    );
  });

  it("Property 10: blank images and comments are not rendered", () => {
    fc.assert(
      fc.property(
        fc.record({
          infographic_image: fc.constantFrom("", "images/a.png"),
          relationship_image: fc.constantFrom("", "images/b.png"),
          comments: fc.constantFrom([], [""], ["  "], ["ความเห็นทดสอบ"]),
        }),
        (fields) => {
          const root = document.createElement("div");
          renderPost(
            {
              id: "01-ทดสอบ",
              title: "ทดสอบ",
              announcement_date: "2026-09-28",
              content_html: "<p>เนื้อหา</p>",
              contentPath: "data/2026-09-28/content.json",
              ...fields,
            },
            root,
          );
          const expected = [fields.infographic_image, fields.relationship_image].filter(Boolean).length;
          expect(root.querySelectorAll("img").length).toBe(expected);
          const hasComment = fields.comments.some((item) => item.trim());
          expect(Boolean(root.querySelector(".comments"))).toBe(hasComment);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("places the summary, images, and comments in that order", () => {
    const root = document.createElement("div");
    renderPost(
      {
        id: "01-ทดสอบ",
        title: "พรบ.ทดสอบ",
        announcement_date: "2026-07-08",
        content_html: "<p>สรุปกฎหมาย</p>",
        infographic_image: "images/01_ภาพ.png",
        relationship_image: "images/01_แผน.png",
        comments: ["โพสต์เฟซบุ๊ก"],
        contentPath: "data/2026-09-28/content.json",
      },
      root,
    );
    const content = root.querySelector(".content");
    const image = root.querySelector("img");
    const comments = root.querySelector(".comments");
    expect(content.compareDocumentPosition(image) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(image.compareDocumentPosition(comments) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(root.querySelector(".comments h3").textContent).toBe("ความเห็น");
  });
});
