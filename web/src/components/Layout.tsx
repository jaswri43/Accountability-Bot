import { Link, NavLink, Outlet } from "react-router-dom";
import { UserMenu } from "./UserMenu";

const NAV: { to: string; label: string; end?: boolean }[] = [
  { to: "/", label: "Overview", end: true },
  { to: "/league", label: "League" },
  { to: "/deadlock", label: "Deadlock" },
  { to: "/players", label: "Players" },
  { to: "/templates", label: "Tasks" },
  { to: "/history", label: "History" },
];

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `flex h-12 shrink-0 items-center border-b-2 px-3 text-sm transition-colors md:h-16 ${
    isActive ? "border-accent font-medium text-fg" : "border-transparent text-muted hover:text-fg"
  }`;

/** Full-width page shell: header bar with text tabs, then the page with
 * ~48px side padding (less on small screens) and no max-width container. */
export function Layout() {
  return (
    <div className="min-h-screen bg-bg text-fg">
      <header className="border-b border-line bg-surface">
        <div className="flex flex-wrap items-center gap-x-6 px-4 sm:px-8 lg:px-12">
          <Link to="/" className="flex h-14 items-center gap-2.5 md:h-16">
            <span className="h-6 w-6 rounded-md bg-accent" aria-hidden="true" />
            <span className="font-semibold tracking-tight">Accountability</span>
          </Link>
          <nav
            aria-label="Main"
            className="order-last -mx-4 flex w-[calc(100%+2rem)] overflow-x-auto px-1 sm:-mx-8 sm:w-[calc(100%+4rem)] sm:px-5 md:order-0 md:mx-0 md:w-auto md:px-0"
          >
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navLinkClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto">
            <UserMenu />
          </div>
        </div>
      </header>
      <main className="px-4 py-8 sm:px-8 lg:px-12 lg:py-10">
        <Outlet />
      </main>
    </div>
  );
}
