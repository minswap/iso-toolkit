export class Duration {
  private _millisecond: number;

  constructor(millisecond: number) {
    this._millisecond = millisecond;
  }

  static newMilliseconds(x: number): Duration {
    return new Duration(x);
  }

  get milliseconds(): number {
    return this._millisecond;
  }

  static newSeconds(x: number): Duration {
    return new Duration(x * 1000);
  }

  get seconds(): number {
    return this._millisecond / 1000;
  }

  static newMinutes(x: number): Duration {
    return new Duration(x * 60 * 1000);
  }

  get minutes(): number {
    return this._millisecond / 1000 / 60;
  }

  static newHours(x: number): Duration {
    return new Duration(x * 60 * 60 * 1000);
  }

  get hours(): number {
    return this._millisecond / 1000 / 60 / 60;
  }

  static newDays(x: number): Duration {
    return new Duration(x * 24 * 60 * 60 * 1000);
  }

  get days(): number {
    return this._millisecond / 1000 / 60 / 60 / 24;
  }

  static newWeeks(x: number): Duration {
    return new Duration(x * 7 * 24 * 60 * 60 * 1000);
  }

  get weeks(): number {
    return this._millisecond / 1000 / 60 / 60 / 24 / 7;
  }

  equals(other: Duration): boolean {
    return this._millisecond === other._millisecond;
  }

  notEquals(other: Duration): boolean {
    return this._millisecond !== other._millisecond;
  }

  lessThan(other: Duration): boolean {
    return this._millisecond < other._millisecond;
  }

  lessThanOrEquals(other: Duration): boolean {
    return this._millisecond <= other._millisecond;
  }

  greaterThan(other: Duration): boolean {
    return this._millisecond > other._millisecond;
  }

  greaterThanOrEquals(other: Duration): boolean {
    return this._millisecond >= other._millisecond;
  }

  // Available resolution: day, hour, minute, second
  // Example: 1d 2h 3m 4.56s
  toString(): string {
    let ms = this._millisecond;
    if (ms === 0) {
      return "0s";
    }
    const parts: string[] = [];

    const days = Math.floor(ms / (1000 * 60 * 60 * 24));
    if (days > 0) {
      parts.push(days + "d");
    }
    ms %= 1000 * 60 * 60 * 24;

    const hours = Math.floor(ms / (1000 * 60 * 60));
    if (hours > 0) {
      parts.push(hours + "h");
    }
    ms %= 1000 * 60 * 60;

    const minutes = Math.floor(ms / (1000 * 60));
    if (minutes > 0) {
      parts.push(minutes + "m");
    }
    ms %= 1000 * 60;

    const seconds = ms / 1000;
    if (seconds > 0) {
      parts.push(seconds + "s");
    }
    return parts.join(" ");
  }

  // Subtract a duration from a date and return a date before
  static before(date: Date, duration: Duration): Date {
    return new Date(date.getTime() - duration.milliseconds);
  }

  // Add a duration to a date and return a date later
  static after(date: Date, duration: Duration): Date {
    return new Date(date.getTime() + duration.milliseconds);
  }

  // Return the duration between 2 dates
  static between(d1: Date, d2: Date): Duration {
    return new Duration(Math.abs(d1.getTime() - d2.getTime()));
  }

  static gennerateTimeSeries(
    start: Date,
    end: Date,
    duration: Duration,
  ): Date[] {
    const timeSeries: Date[] = [];
    let currentDate = new Date(start);

    while (currentDate <= end) {
      timeSeries.push(new Date(currentDate));
      currentDate = Duration.after(currentDate, duration);
    }

    return timeSeries;
  }
}
