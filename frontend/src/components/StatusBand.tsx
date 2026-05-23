type Props = {
  status: string;
  summaryStatus: string;
};

export function StatusBand({ status, summaryStatus }: Props) {
  return (
    <section className="statusBand">
      <span>{status}</span>
      {summaryStatus ? <em>{summaryStatus}</em> : null}
    </section>
  );
}
