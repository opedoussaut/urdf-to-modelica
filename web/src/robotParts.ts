/** Plain-language names for the ALOHA follower arm's joints and the link each one moves (URDF child link). */
export type Part = { joint: string; link: string; name: string; plain: string; expert: string };

export const PARTS: Part[] = [
  { joint: "waist", link: "shoulder_link", name: "Base rotation", plain: "Turns the whole arm left and right, like turning your body.", expert: "Revolute about z · waist" },
  { joint: "shoulder", link: "upper_arm_link", name: "Shoulder", plain: "Lifts the whole arm up and down. It carries the most weight, so two motors drive it.", expert: "Revolute about y · two XM540 servos" },
  { joint: "elbow", link: "upper_forearm_link", name: "Elbow", plain: "Bends the forearm, like your elbow.", expert: "Revolute about y · two XM540 servos" },
  { joint: "forearm_roll", link: "lower_forearm_link", name: "Forearm twist", plain: "Twists the forearm around its own length.", expert: "Revolute about x" },
  { joint: "wrist_angle", link: "wrist_link", name: "Wrist", plain: "Tilts the hand up and down.", expert: "Revolute about y" },
  { joint: "wrist_rotate", link: "gripper_link", name: "Wrist twist", plain: "Rotates the hand, like turning a key.", expert: "Revolute about x" },
  { joint: "left_finger", link: "left_finger_link", name: "Gripper", plain: "Opens and closes the two fingers to hold objects.", expert: "Prismatic fingers (right finger mirrors the left)" },
];

export const partOfJoint = (joint?: string) => PARTS.find((p) => p.joint === joint);
export const partOfLink = (link?: string) => {
  const l = (link || "").split("/").at(-1);
  if (l === "right_finger_link" || l === "fingers_link" || l === "gripper_prop_link" || l === "gripper_bar_link") return PARTS[6];
  return PARTS.find((p) => p.link === l);
};
