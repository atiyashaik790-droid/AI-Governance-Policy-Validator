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
      unsupportedExplanation="Regex mode does not provide this detector."
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
  fireEvent.click(screen.getByRole("checkbox", { name: "Phone Number" }));
  expect(trigger).toHaveTextContent("All 2 supported entities selected");
  fireEvent.keyDown(screen.getByRole("searchbox"), { key: "Escape" });
  expect(trigger).toHaveAttribute("aria-expanded", "false");
  expect(trigger).toHaveFocus();
  fireEvent.click(trigger);
  expect(screen.getByRole("checkbox", { name: "Phone Number" })).toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: /Show unsupported detectors/ }));
  expect(screen.getByText("Regex mode does not provide this detector.")).toBeInTheDocument();
  expect(
    screen.getByRole("checkbox", { name: "Person Name (unavailable)" }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Select All" }));
  expect(trigger).toHaveTextContent("All 2 supported entities selected");
  fireEvent.click(screen.getByRole("button", { name: "Clear Selection" }));
  expect(trigger).toHaveTextContent("All installed PII entities (default)");
  fireEvent.click(screen.getByRole("button", { name: "Done" }));
  expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
});

it("offers the same three actions for moderation categories", () => {
  const Moderation = () => {
    const [selected, setSelected] = useState<string[]>([]);
    return <MultiSelectDropdown label="Moderation category selection" options={["hate", "violence"]}
      selected={selected} allLabel="All moderation categories (default)" onChange={setSelected} />;
  };
  render(<Moderation />);
  const trigger = screen.getByRole("button", { name: "Moderation category selection" });
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole("button", { name: "Select All" }));
  expect(trigger).toHaveTextContent("All 2 categories selected");
  fireEvent.click(screen.getByRole("button", { name: "Clear Selection" }));
  expect(trigger).toHaveTextContent("All moderation categories (default)");
  fireEvent.click(screen.getByRole("button", { name: "Done" }));
  expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
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
    screen.queryByRole("checkbox", { name: "Email Address" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("checkbox", { name: "Phone Number" }),
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

it("keeps loaded PII selections when the editor opens and closes", () => {
  const change = vi.fn();
  render(<MultiSelectDropdown label="PII entity selection" options={["EMAIL_ADDRESS", "IN_AADHAAR", "IN_PAN"]}
    selected={["IN_AADHAAR"]} available={["EMAIL_ADDRESS", "IN_AADHAAR", "IN_PAN"]}
    allLabel="All installed PII entities (default)" onChange={change} />);
  const trigger = screen.getByRole("button", { name: "PII entity selection" });
  expect(trigger).toHaveTextContent("1 selected: IN_AADHAAR");
  fireEvent.click(trigger);
  expect(screen.getByRole("checkbox", { name: "Aadhaar Number" })).toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Done" }));
  expect(trigger).toHaveTextContent("1 selected: IN_AADHAAR");
  expect(change).not.toHaveBeenCalled();
});

it("shows saved hidden entities and selects only visible supported PII", () => {
  const Editor = () => {
    const [selected, setSelected] = useState(["LOCATION"]);
    return <MultiSelectDropdown label="PII entity selection" options={["EMAIL_ADDRESS", "IN_PAN"]}
      selected={selected} available={["EMAIL_ADDRESS", "IN_PAN", "LOCATION"]}
      allLabel="All installed PII entities (default)" onChange={setSelected} />;
  };
  render(<Editor />);
  fireEvent.click(screen.getByRole("button", { name: "PII entity selection" }));
  expect(screen.getByRole("checkbox", { name: "LOCATION" })).toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Select All" }));
  expect(screen.getByRole("button", { name: "PII entity selection" })).toHaveTextContent("All 2 supported entities selected");
  expect(screen.queryByRole("checkbox", { name: "LOCATION" })).not.toBeInTheDocument();
});
