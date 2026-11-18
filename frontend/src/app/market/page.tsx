import { redirect } from "next/navigation";

// The market page and the board are the same surface; keep one canonical route.
export default function MarketPage() {
  redirect("/value-bets");
}
