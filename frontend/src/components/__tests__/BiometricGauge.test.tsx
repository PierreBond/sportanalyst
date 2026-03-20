import { render, screen } from "@testing-library/react";
import { BiometricGauge } from "../BiometricGauge";

describe("BiometricGauge", () => {
  it("renders label and value", () => {
    render(<BiometricGauge label="ACWR" value={1.2} />);

    expect(screen.getByText("ACWR")).toBeInTheDocument();
    expect(screen.getByText("1.2")).toBeInTheDocument();
  });

  it("displays normal status for value in range", () => {
    render(<BiometricGauge label="HRV" value={50} min={0} max={100} thresholds={{ low: 30, high: 70 }} />);

    expect(screen.getByText("Normal")).toBeInTheDocument();
  });

  it("displays low status for value below threshold", () => {
    render(<BiometricGauge label="HRV" value={20} min={0} max={100} thresholds={{ low: 30, high: 70 }} />);

    expect(screen.getByText("Low")).toBeInTheDocument();
  });

  it("displays high status for value above threshold", () => {
    render(<BiometricGauge label="HRV" value={80} min={0} max={100} thresholds={{ low: 30, high: 70 }} />);

    expect(screen.getByText("High")).toBeInTheDocument();
  });

  it("displays unit when provided", () => {
    render(<BiometricGauge label="Heart Rate" value={65} unit="bpm" />);

    expect(screen.getByText("bpm")).toBeInTheDocument();
  });
});
