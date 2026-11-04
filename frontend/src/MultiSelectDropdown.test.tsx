import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MultiSelectDropdown } from "./MultiSelectDropdown";

afterEach(cleanup);

function Example({ disabled = false }: { disabled?: boolean }) {
  const [selected, setSelected] = useState(["EMAIL_ADDRESS"]);
  return (
    <MultiSelectDropdown
      label="PII entity selection"
      options={["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON"]}
      selected={selected}
      available={["EMAIL_ADDRESS", "PHONE_NUMBER"]}
      allLabel="All installed PII entities (default)"
      disabled={disabled}
      onChange={setSelected}
    />
  );
}

it("keeps a compact summary, supports multiple selections and restores focus on Escape", () => {
  render(<Example />);
  const trigger = screen.getByRole("button", { name: "PII entity selection" });
  expect(trigger).toHaveTextContent("1 selected: EMAIL_ADDRESS");
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  fireEvent.click(trigger);
  expect(screen.getByRole("searchbox")).toHaveFocus();
  fireEvent.click(screen.getByRole("checkbox", { name: "PHONE_NUMBER" }));
  expect(trigger).toHaveTextContent("2 selected: EMAIL_ADDRESS, PHONE_NUMBER");
  fireEvent.keyDown(screen.getByRole("searchbox"), { key: "Escape" });
  expect(trigger).toHaveAttribute("aria-expanded", "false");
  expect(trigger).toHaveFocus();
  fireEvent.click(trigger);
  expect(screen.getByRole("checkbox", { name: "PHONE_NUMBER" })).toBeChecked();
  expect(
    screen.getByRole("checkbox", { name: "PERSON (unavailable)" }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Use all (default)" }));
  expect(trigger).toHaveTextContent("All installed PII entities (default)");
});

it("searches without submitting the policy form and closes on outside click", () => {
  const submit = vi.fn((event) => event.preventDefault());
  render(
    <form onSubmit={submit}>
      <Example />
      <button type="submit">Save policy</button>
    </form>,
  );
  fireEvent.click(screen.getByRole("button", { name: "PII entity selection" }));
  const search = screen.getByRole("searchbox");
  fireEvent.change(search, { target: { value: "phone" } });
  expect(
    screen.queryByRole("checkbox", { name: "EMAIL_ADDRESS" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("checkbox", { name: "PHONE_NUMBER" }),
  ).toBeInTheDocument();
  fireEvent.keyDown(search, { key: "Enter" });
  expect(submit).not.toHaveBeenCalled();
  fireEvent.mouseDown(document.body);
  expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
});

it("prevents editing in read-only mode", () => {
  render(<Example disabled />);
  expect(
    screen.getByRole("button", { name: "PII entity selection" }),
  ).toBeDisabled();
});
