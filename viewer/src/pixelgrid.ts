/** A grid of painted pixels (a colour or empty), for sprites drawn in code one pixel at a time. */
export class PixelGrid {
  readonly width: number;
  readonly height: number;
  readonly cells: (string | null)[];

  constructor(width: number, height: number) {
    this.width = width;
    this.height = height;
    this.cells = new Array<string | null>(width * height).fill(null);
  }

  set(x: number, y: number, colour: string): void {
    const column = Math.round(x);
    const row = Math.round(y);
    if (column >= 0 && column < this.width && row >= 0 && row < this.height) this.cells[row * this.width + column] = colour;
  }

  get(x: number, y: number): string | null {
    return x < 0 || x >= this.width || y < 0 || y >= this.height ? null : (this.cells[y * this.width + x] ?? null);
  }

  /** A run of pixels along row `y` from `x0` to `x1`, both included. */
  row(x0: number, x1: number, y: number, colour: string): void {
    for (let x = x0; x <= x1; x += 1) this.set(x, y, colour);
  }

  rect(x: number, y: number, width: number, height: number, colour: string): void {
    for (let row = 0; row < height; row += 1) this.row(x, x + width - 1, y + row, colour);
  }

  /** Ring every painted pixel with `colour` on the empty cells beside it. */
  outline(colour: string): void {
    const edge: number[] = [];
    for (let y = 0; y < this.height; y += 1) {
      for (let x = 0; x < this.width; x += 1) {
        if (this.get(x, y) !== null) continue;
        if ([[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dy]) => this.get(x + (dx ?? 0), y + (dy ?? 0)) !== null)) edge.push(y * this.width + x);
      }
    }
    for (const index of edge) this.cells[index] = colour;
  }

  toCanvas(): HTMLCanvasElement {
    const canvas = document.createElement("canvas");
    canvas.width = this.width;
    canvas.height = this.height;
    const ctx = canvas.getContext("2d");
    if (ctx === null) return canvas;
    this.cells.forEach((colour, index) => {
      if (colour === null) return;
      ctx.fillStyle = colour;
      ctx.fillRect(index % this.width, Math.floor(index / this.width), 1, 1);
    });
    return canvas;
  }
}
