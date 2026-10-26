/** Plain-language explanations of everything that can go wrong in the engineering pipeline.
 * Each entry answers three questions for a non-specialist: what happened, why it matters, what usually fixes it.
 * Shown in collapsible "What went wrong, in simple terms" notes next to every failure. */
export type Why = { what: string; matters: string; fix: string };

/** Stage 2 steps (kkh/workflow/stage2_check.STEPS), when the step fails. */
export const STEP_WHY: Record<string, Why> = {
  load: {
    what: "OpenModelica could not even read the model files: the text is not valid Modelica (a typo, a missing semicolon) or it names a library or class that does not exist.",
    matters: "Nothing else can be checked until the files can be read, so every later step is skipped.",
    fix: "Correct the line OpenModelica points to, or the class name it cannot find (for example an old MSL 3 name such as Modelica.SIunits used with MSL 4).",
  },
  structure: {
    what: "The files can be read, but a part refers to something that does not exist or does not fit: a misspelled component, a wrong type, a parameter of the wrong kind.",
    matters: "OpenModelica cannot assemble the robot from its parts, so it cannot be simulated.",
    fix: "Correct the component or class name, or the parameter, named in the message.",
  },
  balance_translation: {
    what: "The model does not have exactly one equation per unknown, or its equations cannot be put in an order a computer can solve. Usually a connection is missing or doubled, or an initial condition contradicts another.",
    matters: "A physics model must be exactly determined; with one equation too many or too few there is no unique answer to compute.",
    fix: "Look for a deleted or duplicated connection between parts, or an extra initial equation, near the part the message names.",
  },
  simulation: {
    what: "The model is complete but the simulation stopped: the computer could not find a consistent start, or the motion became impossible to compute.",
    matters: "A model that cannot run cannot be used to predict anything.",
    fix: "Check start values and initial conditions (for example a joint starting outside its limits) and any value that makes a quantity infinite.",
  },
  urdf_consistency: {
    what: "The model runs, but it does not behave like the robot file: a part ends up in the wrong place when the joints move, a mass or axis differs, or the motor torques do not match an independent physics engine.",
    matters: "A model that runs but describes another robot is the most dangerous kind of error: it looks fine and gives wrong answers.",
    fix: "Find the first joint on the chain where the parts drift away (it is named), then compare its origin, axis and limits with the robot file.",
  },
  records: {
    what: "A value stored in the model (mass, centre of mass, inertia, joint origin, axis or limit) differs from the value in the robot file.",
    matters: "Robot values must come from the robot file; a changed value changes the robot.",
    fix: "Restore the value from the robot file.",
  },
  graphics: {
    what: "Some connections between parts are not drawn in the diagram, or a block sits outside the drawing area.",
    matters: "Only the picture is affected, not the physics. It is reported separately and never decides the verdict.",
    fix: "The layout pass after approval draws the missing lines automatically.",
  },
};

/** Stage 2 verdicts (the first gate a model fails). */
export const VERDICT_WHY: Record<string, string> = {
  "fails at load": "The model files cannot be read by OpenModelica, so nothing else could be checked.",
  "fails at structure": "The files are readable, but the model cannot be assembled from its parts.",
  "fails at balance_translation": "The model is assembled, but its equations do not add up to a solvable system.",
  "compiles, does not simulate": "The model is complete and accepted by OpenModelica, but the simulation stops.",
  "simulates, engineering checks fail":
    "The model runs, but it does not match the robot file everywhere. Running is not enough: the comparison with the robot file is what makes a model trustworthy.",
};

/** Finding categories (kkh/workflow/stage2_check.CATEGORIES). */
export const CATEGORY_WHY: Record<string, string> = {
  "syntax and translation": "The text of the model is not valid Modelica, or OpenModelica could not translate it into equations.",
  "missing class or library": "The model names a building block that does not exist: a typo, or a name from an older library version.",
  "type and unit": "A value has the wrong kind or unit, for example degrees where radians are expected.",
  "connector and equation": "Parts are not connected the way they should be: a connection is missing, doubled or points to something that does not exist, so the equations do not add up.",
  "initialization and numerical": "The model cannot find a consistent starting state, or a start value contradicts a limit or another equation.",
  "unsupported URDF element": "Part of the robot file is ignored or rewritten by the converter (for example ros2_control, or a mimic joint that is recorded but not used).",
  "mechanical or kinematic inconsistency": "The model moves differently from the robot file: a part ends up in the wrong place, or an axis, mass or torque differs.",
  "graphical annotation": "Only the diagram drawing is affected (a missing line or a misplaced block), never the physics.",
  other: "A problem OpenModelica reports that does not fit the other groups; the message itself says what it is.",
};

/** Messages that deserve a more specific explanation than their category. */
export const MESSAGE_WHY: [RegExp, string][] = [
  [/mimic/i, "In the robot file one finger copies the other (a “mimic” joint). The converter stored that rule but does not apply it, so the finger moves on its own and ends up in the wrong place."],
  [/below its lower|above its upper|outside .*limit/i, "The test model starts this joint outside the range the robot file allows. A real robot could not start there."],
  [/initial conditions are not fully specified/i, "OpenModelica had to guess some starting values. This is common and usually harmless, but it is reported so nothing is hidden."],
  [/package:_\/|mesh URI/i, "The converter rewrote the path to a 3D shape so that no tool can find it. Only the picture is affected; the downloads of the studio repair it."],
  [/ros2_control/i, "The robot file describes its motor controllers for ROS 2. A physics model does not need them, so the converter ignores them."],
  [/imbalanced|equations .* variables/i, "The model has one equation too many or too few. Usually a connection between two parts was removed or doubled."],
  [/not found in scope/i, "The model uses a name that does not exist in that place: a typo, or a class from another library version."],
  [/Missing token/i, "A character is missing in the model text, typically a semicolon at the end of a line."],
];

export function messageWhy(message: string, category?: string): string | undefined {
  const hit = MESSAGE_WHY.find(([rx]) => rx.test(message || ""));
  return hit ? hit[1] : category ? CATEGORY_WHY[category] : undefined;
}

/** Outcome of a repair method on one case (kkh/workflow/stage4_validate). */
export const STATE_WHY: Record<string, string> = {
  unchanged:
    "No edit was applied, so the model is exactly as before: either the AI proposed none, or its proposals could not be applied (each edit must replace an exact piece of text that appears once in the file).",
  "not improved": "Edits were applied, but the independent check finds the model no better than before: the problems it fixed were replaced by others, or nothing important changed.",
  regressed: "Edits were applied and the model got worse: it now fails at an earlier check than before (for example it no longer simulates).",
  "rejected (integrity)":
    "The edits broke a safety rule, so the result is rejected even if it compiles: a part, a connection or a check was deleted, a value from the robot file was changed, or only the drawing was edited to hide a problem.",
  improved: "The model is better than before (it passes a later check, or more problems were solved than created), but not every engineering check passes yet, so it is not validated. An engineer can review it.",
  "not run": "This method has not been run on this case.",
};

/** Integrity flags (kkh/workflow/stage4_validate.integrity). */
export const FLAG_WHY: Record<string, string> = {
  "file deleted": "A model file was removed.",
  "file added": "A new file was added to the robot package.",
  "annotation-only edit": "Only the drawing information changed, not the model itself.",
  "assertion removed": "A built-in safety check of the model was deleted.",
  "connection removed": "A connection between two parts was deleted.",
  "component removed": "A part or joint of the robot was deleted.",
  "assertion level changed": "A safety check was weakened (from error to warning).",
  "URDF value changed": "A value that comes from the robot file (mass, position, axis, limit) was changed.",
};

/** Stage 0 verdicts. */
export const COMPLIANCE_WHY: Record<string, string> = {
  "not compliant":
    "The robot file breaks the official URDF rules (a required element is missing, a value has the wrong format) or its parts do not form a single tree. Converting it would only move the problem into the physics model, so the studio stops here.",
  "physically implausible":
    "The file follows the URDF rules, but some values describe something no real object can be, for example a negative mass or an impossible inertia, or a lower joint limit above the upper one. The conversion is refused until the values are corrected.",
  "compliant with warnings": "The file is valid; the warnings point to values worth checking, such as an axis that is not of length one.",
};
