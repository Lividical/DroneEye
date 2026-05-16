// This script is Java Script. It is used to be the middle man of the three other langauges. This communicate for each of them and does logical controls

let currentState = "Stopped";		// starting at stopped
let trackingEnabled = false;		// starting at no tracking
let lastAngle = null;			// last angle is nothing at start
let lastX = null;			// last x is nothing at start
let lastLogLen = -1;			// log is nothing at start
let lastLogTimeStamp = "";			// nothing in log

function updateTrackingButton() {	// changes the button on CSS
	const btn = document.getElementById("trackingBtn");
	if (!btn) return;	// button is false nothing was found
	
	btn.textContent = trackingEnabled ? "Tracking: ON" : "Tracking: OFF";	// if tracking is true/false 
										// it sets the text

	if (trackingEnabled) {
		btn.classList.add("active");	// makes the CSS see active for the btn
		btn.classList.remove("inactive");	// removes the inactive on the btn on CSS
	} else {
		btn.classList.add("inactive");	// makes the CSS see incactive for the btn
		btn.classList.remove("active");	// removes the inactive on the btn on CSS
	}
}

function updateMainStatus() {	// changes the text in the status box
	const valueBox = document.getElementById("value");	// looks in html for id value and stores in valuebox
	if (!valueBox) return;	// valueBox has nothing in it
	
	if (trackingEnabled) {
		valueBox.textContent = "Tracking is ON";	// tracking in status box
	} else {
		valueBox.textContent = currentState;		// state in status box
	}
}

window.addEventListener("keydown", handleKey, {passive: false });	// makes a detector for key down
window.addEventListener("load", () => { document.body.focus(); });	// listens for loads
document.addEventListener("click", () => { document.body.focus(); });	// listens for clicks

async function refreshServoState() {
	try{
		const r = await fetch("/value");	// request value
		const data = await r.json();		// wait for response and stor in data
	
		currentState = data.servo_state;	// get out of data servo_state
		trackingEnabled = !!data.tracking;	// get of out of data tracking
		
		updateMainStatus();			// call update main status
		updateTrackingButton();			// call tracking btn update
	} catch (e) {
		console.error("Failed to refresh servo state:", e);
	}
}

function handleKey(e) {	// e is the an event object of the key that is pressed
	let next = null;	// next will be the state it will become after figuring out what was pressed

	if (e.key === "ArrowLeft") next = "Left";		// this is the left arrow press, go left
	else if (e.key === "ArrowRight") next = "Right";		// this is the right arrow press, go right
	else if (e.key === "ArrowDown") next = "Stopped";	// This is the down arrow press, stop
	else if (e.key === "r" || e.key === "R") {		// r or R being pressed
		e.preventDefault();				// in case this key press of r or R has something 								// with it ignore that then
		resetLog();					// resets the log
		return;
	} else { return; }						// none of the above 
	
	e.preventDefault();					// stops arrow keys normal actions
	
	if (next === currentState && !trackingEnabled) return;	// dont do anything if same state or tracking is on
	
	// next state is not current and tracking is off so change current state
	change(next);
}

async function refreshCoords(){	// waits for server requests to refresh coords
	try{
		const r = await fetch("/coords");	// request on python value waits till response and stores r
		const data = await r.json();		// turns the JSON in to javascript object
		
		if (data.x === -1 || data.y === -1) return;	// defaults
		
		if (data.x !== lastX || data.y !== lastY) {
			lastX = data.x;		// update last x
			lastY = data.y;		// update last y
			document.getElementById("coords").textContent = "x: " + data.x + ", y: " + data.y; // update
													  // html
		}
	}catch (e) {
		console.error("Failed to refresh coords:", e);
	}
}
		


async function refreshAngle(){
		
	try{
		const r = await fetch("/angle");
		const data = await r.json();		

		if (data.angle === null || data.angle === undefined){ // the angle is nothing
			document.getElementById("angleBox").textContent = "angle: unavailable";	// update html
			return;
		}
			
		const angle = Number(data.angle).toFixed(0);		// angle data to number format no decimal
		if ( angle !== lastAngle) {	// check if angle changed
			lastAngle = angle; 	// new angle update
			document.getElementById("angleBox").textContent = "angle: " + angle;	// update html
		}
	} catch (e) {	// failure happened
		document.getElementById("angleBox").textContent = "angle: unavailable";		// update html
	}
}

async function change(direction) {	// changes the direction
	try {
		const r = await fetch("/change", { // request for /change on python code
			method: "POST",		   // post ones
			headers: { "Content-Type": "application/json" },	// all formating
			body: JSON.stringify( { direction: direction} ) 	// the JSON 
		} );
	
		const data = await r.json();	// waits for the request data
		currentState = data.servo_state;	// set up new servo_state
		
		updateMainStatus();	// refresh main box status
	} catch (e){
		console.error("Failed to change direction:", e);
	}
}

async function toggleTracking(){
	const newEnabled = !trackingEnabled;	// flips the current enabled boolean
	
	try{
		const r = await fetch("/tracking", {	// request for /tracking and formating below
			method: "POST",
			headers: { "Content-Type": "application/json"},
			body: JSON.stringify( { enabled: newEnabled } )
		} ) ;	
		
		const data = await r.json();		// wait for data
		
		trackingEnabled = !!data.tracking;	// turns into a true boolean
		currentState = data.servo_state;	// update current state
		
		updateMainStatus();			// update the main status
		updateTrackingButton();			// update the tracking button
	} catch (e) {	// failed to toggle tracking button
		console.error("Failed to toggle tracking:", e);
	}
}

async function refreshLog(force = false){	// start refresh log as false making only update when pass
 						// something in it
	try{
		const r = await fetch("/log.json");	// request /log
		const data = await r.json();		// wait till /log responds
		
		const entries = data.entries || [];	// data = entries or nothing
		const windowStartTime = data.window_start || "?";	// log window start time or nothing
		
		let lastTimeStamp = "";		// last time stamp is nothing
		if (entries.length > 0) lastTimeStamp = entries[entries.length -1].ts	// if something in log add
											// to last time stamp 
											// entries time stamp
		// if not force, entries length and last length, last time stamp and last log time stamnp equal
		// return
		if (!force && entries.length === lastLogLen && lastTimeStamp === lastLogTimeStamp) return;
		
		// if not change them
		lastLogLen = entries.length;		// update log len
		lastLogTimeStamp = lastTimeStamp;	// update log time stamp
		
		// update the html
		document.getElementById("logMeta").textContent = "Window start: " + windowStartTime + " | entries: " + entries.length;
	
		const show = entries.slice(-200);	// keep only the last 200 log entries

		let text = "";
		
		for (const entry of show) {	// loop through to add to text in correct formating
			text += entry.ts + " x=" + entry.x + " y=" + entry.y + "\n";
		}

		if (text === "") text = "(empty)"; // no text meaning no logs
		
		document.getElementById("logList").textContent = text;	// update the html
	} catch (e) {
		console.error("Failed to refresh log:", e);
	}
}

async function resetLog() {	// reset the log
	try{
		await fetch("/log/reset", {method: "POST" });	// request for /log/reset
		lastLogLen = -1;	// update to default log len
		lastLogTimeStamp = "";	// update log time stamp to default
		await refreshLog(true);		// wait for refresh log and force is true so update
	} catch (e) {
		console.error("Failed to reset log:", e);
	}
}

window.addEventListener("load", () => {		// when page loads run this code
	const trackingBtn = document.getElementById("trackingBtn");	// get tracking btn from html
	if (trackingBtn) {
		trackingBtn.addEventListener("click", toggleTracking);	// tracks for clicks on the button if does 
									// toggle tracking function is called
	}
	
	refreshServoState();	// update servo state
	refreshCoords();	// update coords
	refreshAngle();		// update angle
	refreshLog();		// update log
});

// the following below makes it so evern # of milliseconds it will call them
setInterval(refreshCoords, 500);
setInterval(refreshAngle, 500);
setInterval(refreshLog, 500);
setInterval(refreshServoState, 500);




























	
