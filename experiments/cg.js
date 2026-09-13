import { Chess } from "./node_modules/chess.js/dist/esm/chess.js";
import { Chessground } from "./node_modules/chessground/dist/chessground.js";
import { checkEmpassant, getLegalMoves, checkPromotion } from "./utils.js";
import { PromotionDialog } from "./promotion.js";
let container = document.querySelector("div.chess-container");

let blackFen = "8/2r5/1k5p/1pp4P/8/K2P4/PR2QB2/2q5 b - - 0 1";
let whiteFen = "8/6P1/8/8/8/8/4k3/2K5 w - - 0 1";
let game = new Chess(whiteFen);

const toColor = (chess) => {
  return chess.turn() === "w" ? "white" : "black";
};
let cboard = Chessground(container, {
  fen: whiteFen,
  orientation: "white",
  turnColor: toColor(game),
  movable: { free: false, color: "both", dests: getLegalMoves(game) },
});
cboard.set({
  movable: {
    events: { after: handleMove(cboard, game) },
  },
});
const promotionDialog = new PromotionDialog(document.body, container, cboard);

function handleMove(cg, chess) {
  return (orig, dest) => {
    if (checkPromotion(orig, dest, chess)) {
      try {
        promotionDialog.show(chess.turn(), (piece) => {
          chess.move({ from: orig, to: dest, promotion: piece });
          console.log(chess.fen());
          cg.set({
            viewOnly: false,
            fen: chess.fen(),
            turnColor: toColor(chess),
            movable: {
              free: false,
              color: "both",
              dests: getLegalMoves(chess),
            },
            check: chess.inCheck(),
          });
        });
      } catch (error) {
        window.alert(error);
      }
      return;
    }
    if (checkEmpassant(orig, dest, chess)) {
      chess.move({ from: orig, to: dest });
      cg.set({
        fen: chess.fen(),
        turnColor: toColor(chess),
        movable: {
          free: false,
          color: "both",
          dests: getLegalMoves(chess),
        },
      });
    } else {
      chess.move({ from: orig, to: dest });
      cg.set({
        fen: chess.fen(),
        turnColor: toColor(chess),
        movable: {
          free: false,
          color: "both",
          dests: getLegalMoves(chess),
        },
        check: chess.inCheck(),
      });
    }
  };
}

function resetBoard() {
  game.reset(); // reset the chess.js game to start position
  cboard.set({
    fen: game.fen(),
    turnColor: "white",
    movable: {
      free: false,
      color: "both",
      dests: getLegalMoves(game),
    },
    check: false,
  });
}
