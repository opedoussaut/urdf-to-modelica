within ALOHA2.Blocks;
function cosineBlend "Position (order 0), velocity (1) or acceleration (2) of a cosine-blended waypoint path"
  extends Modelica.Icons.Function;
  input Real t "Time";
  input Real t_wp[:] "Waypoint times (strictly increasing)";
  input Real q_wp[size(t_wp, 1)] "Waypoint values";
  input Integer order "0: position, 1: velocity, 2: acceleration";
  output Real y;
protected
  Integer nWp = size(t_wp, 1);
  Integer k = nWp - 1;
  Real T, s, dq;
algorithm
  if t <= t_wp[1] then
    y := if order == 0 then q_wp[1] else 0;
  elseif t >= t_wp[nWp] then
    y := if order == 0 then q_wp[nWp] else 0;
  else
    for i in 1:nWp - 1 loop
      if t < t_wp[i + 1] then
        k := i;
        break;
      end if;
    end for;
    T := t_wp[k + 1] - t_wp[k];
    s := (t - t_wp[k]) / T;
    dq := q_wp[k + 1] - q_wp[k];
    if order == 0 then
      y := q_wp[k] + dq * (1 - cos(Modelica.Constants.pi * s)) / 2;
    elseif order == 1 then
      y := dq * Modelica.Constants.pi / (2 * T) * sin(Modelica.Constants.pi * s);
    else
      y := dq * (Modelica.Constants.pi / T)^2 / 2 * cos(Modelica.Constants.pi * s);
    end if;
  end if;
end cosineBlend;
