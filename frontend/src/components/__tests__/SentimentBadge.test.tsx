import { render, screen } from "@testing-library/react";
import { SentimentBadge } from "../SentimentBadge";

describe("SentimentBadge", () => {
  it("renders very positive sentiment correctly", () => {
    render(<SentimentBadge score={0.8} />);

    expect(screen.getByText("Very Positive")).toBeInTheDocument();
  });

  it("renders positive sentiment correctly", () => {
    render(<SentimentBadge score={0.4} />);

    expect(screen.getByText("Positive")).toBeInTheDocument();
  });

  it("renders neutral sentiment correctly", () => {
    render(<SentimentBadge score={0.0} />);

    expect(screen.getByText("Neutral")).toBeInTheDocument();
  });

  it("renders negative sentiment correctly", () => {
    render(<SentimentBadge score={-0.4} />);

    expect(screen.getByText("Negative")).toBeInTheDocument();
  });

  it("renders very negative sentiment correctly", () => {
    render(<SentimentBadge score={-0.8} />);

    expect(screen.getByText("Very Negative")).toBeInTheDocument();
  });

  it("displays volume when provided", () => {
    render(<SentimentBadge score={0.5} volume={1500} showVolume={true} />);

    expect(screen.getByText("(1,500)")).toBeInTheDocument();
  });

  it("hides volume when showVolume is false", () => {
    render(<SentimentBadge score={0.5} volume={1500} showVolume={false} />);

    expect(screen.queryByText("(1,500)")).not.toBeInTheDocument();
  });
});
