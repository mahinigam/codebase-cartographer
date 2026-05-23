import CartographerApp from "./CartographerApp";

export const dynamic = "force-dynamic";

export default function Page() {
  return (
    <CartographerApp
      defaultRepoPath={process.env.NEXT_PUBLIC_DEFAULT_REPO ?? ""}
    />
  );
}
